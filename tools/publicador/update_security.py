"""Verify detached update signatures with Windows' cryptographic provider.

Only the locally installed public key is trusted. No key from a release is used.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import ctypes
from ctypes import wintypes
import struct
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def github_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.hostname not in ('github.com', 'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'codeload.github.com')):
        raise ValueError('Endereço de atualização fora dos servidores autorizados do GitHub.')
    return url


def fetch_signature(url):
    with urlopen(Request(github_url(url), headers={'User-Agent': 'Engelmig-Atualizador'}), timeout=20) as response:
        github_url(response.geturl())
        raw = response.read(16385)
    if len(raw) > 16384:
        raise ValueError('Assinatura excede o limite de tamanho.')
    return json.loads(raw)


def verify(archive, metadata, expected_version, root):
    root = Path(root)
    key = root / 'security' / 'update-public.xml'
    if not key.is_file():
        raise ValueError('Chave pública de atualização ainda não configurada. Não publique esta versão de preparação.')
    if not isinstance(metadata, dict) or metadata.get('algorithm') != 'RSA-SHA256':
        raise ValueError('Formato de assinatura inválido.')
    if metadata.get('version') != expected_version or not re.fullmatch(r'\d+\.\d+\.\d+', expected_version):
        raise ValueError('A assinatura não corresponde à versão solicitada.')
    digest = file_hash(archive)
    if metadata.get('sha256') != digest:
        raise ValueError('O pacote foi alterado após a assinatura.')
    try:
        signature = metadata['signature']
        if not isinstance(signature, str) or not 384 <= len(base64.b64decode(signature, validate=True)) <= 1024:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ValueError('Assinatura inválida.') from None
    if os.name != 'nt':
        raise ValueError('Verificação nativa de assinatura disponível no Windows.')
    message = ('Engelmig-update-v1\n' + expected_version + '\n' + digest + '\n').encode('utf-8')
    verify_rsa_windows(key, message, base64.b64decode(signature, validate=True))
    return digest


def public_blob(key):
    raw = Path(key).read_bytes()
    if len(raw) > 16384:
        raise ValueError('Chave pública muito grande.')
    document = ET.fromstring(raw)
    if document.tag != 'RSAKeyValue' or len(document) != 2 or {c.tag for c in document} != {'Modulus', 'Exponent'}:
        raise ValueError('Arquivo deve conter somente a chave pública RSA.')
    modulus = base64.b64decode(document.findtext('Modulus'), validate=True)
    exponent = base64.b64decode(document.findtext('Exponent'), validate=True)
    bits = int.from_bytes(modulus, 'big').bit_length()
    if bits < 3072 or bits > 8192 or bits != len(modulus) * 8 or int.from_bytes(exponent, 'big') != 65537:
        raise ValueError('Parâmetros inválidos na chave pública RSA.')
    # BCRYPT_RSAKEY_BLOB header, then big-endian exponent and modulus.
    return struct.pack('<6I', 0x31415352, bits, len(exponent), len(modulus), 0, 0) + exponent + modulus


def verify_rsa_windows(key, message, signature):
    """RSA PKCS#1 v1.5 / SHA256 via Windows CNG; no executable or script."""
    blob = public_blob(key)
    digest = hashlib.sha256(message).digest()
    api = ctypes.WinDLL('bcrypt.dll')
    handle = ctypes.c_void_p
    status = ctypes.c_int32
    api.BCryptOpenAlgorithmProvider.argtypes = [ctypes.POINTER(handle), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.ULONG]
    api.BCryptOpenAlgorithmProvider.restype = status
    api.BCryptImportKeyPair.argtypes = [handle, handle, wintypes.LPCWSTR, ctypes.POINTER(handle), ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG]
    api.BCryptImportKeyPair.restype = status
    api.BCryptVerifySignature.argtypes = [handle, ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG]
    api.BCryptVerifySignature.restype = status
    api.BCryptDestroyKey.argtypes = [handle]
    api.BCryptDestroyKey.restype = status
    api.BCryptCloseAlgorithmProvider.argtypes = [handle, wintypes.ULONG]
    api.BCryptCloseAlgorithmProvider.restype = status
    class Padding(ctypes.Structure):
        _fields_ = [('pszAlgId', wintypes.LPCWSTR)]
    algorithm, imported = handle(), handle()
    try:
        if api.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm), 'RSA', None, 0) != 0:
            raise ValueError('Não foi possível iniciar a verificação de assinatura no Windows.')
        buffer = ctypes.create_string_buffer(blob)
        if api.BCryptImportKeyPair(algorithm, None, 'RSAPUBLICBLOB', ctypes.byref(imported), buffer, len(blob), 0) != 0:
            raise ValueError('A chave pública foi recusada pelo Windows.')
        padding = Padding('SHA256')
        digest_buffer, signature_buffer = ctypes.create_string_buffer(digest), ctypes.create_string_buffer(signature)
        if api.BCryptVerifySignature(imported, ctypes.byref(padding), digest_buffer, len(digest), signature_buffer, len(signature), 2) != 0:
            raise ValueError('Assinatura da atualização recusada. Nenhum arquivo foi instalado.')
    finally:
        if imported.value:
            api.BCryptDestroyKey(imported)
        if algorithm.value:
            api.BCryptCloseAlgorithmProvider(algorithm, 0)
