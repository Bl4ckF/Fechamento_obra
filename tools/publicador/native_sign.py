"""Sign with the existing user-scoped DPAPI key, using Windows APIs only."""
import base64
import ctypes as c
import hashlib
import os
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


def encrypted_key(path):
    raw = Path(path).read_bytes()
    if len(raw) > 128*1024:
        raise ValueError('Arquivo de chave excede o tamanho esperado.')
    doc = ET.fromstring(raw)
    values = [n.text for n in doc.iter() if n.tag.rsplit('}', 1)[-1] == 'SS']
    if len(values) != 1 or not values[0]:
        raise ValueError('Formato de chave protegida não reconhecido.')
    try:
        return bytes.fromhex(values[0])
    except ValueError:
        raise ValueError('Chave protegida inválida.') from None


def unprotect(data):
    class Blob(c.Structure):
        _fields_ = [('size', c.c_uint32), ('data', c.c_void_p)]
    api = c.WinDLL('crypt32.dll', use_last_error=True)
    kernel = c.WinDLL('kernel32.dll', use_last_error=True)
    api.CryptUnprotectData.argtypes = [c.POINTER(Blob), c.c_void_p, c.c_void_p,
                                      c.c_void_p, c.c_void_p, c.c_uint32, c.POINTER(Blob)]
    api.CryptUnprotectData.restype = c.c_int32
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    buffer = c.create_string_buffer(data)
    source, target = Blob(len(data), c.cast(buffer, c.c_void_p)), Blob()
    if not api.CryptUnprotectData(c.byref(source), None, None, None, None, 1, c.byref(target)):
        raise ValueError('Não foi possível abrir a chave. Use a mesma conta e computador que a criaram. Código Windows: '+str(c.get_last_error()))
    try:
        return c.string_at(target.data, target.size).decode('utf-16-le')
    finally:
        if target.data:
            c.memset(target.data, 0, target.size)
            kernel.LocalFree(target.data)


def private_blob(xml, public_path):
    doc = ET.fromstring(xml)
    public = ET.parse(public_path).getroot()
    if doc.tag != 'RSAKeyValue':
        raise ValueError('Chave privada em formato inválido.')
    def number(node, name):
        return base64.b64decode(node.findtext(name) or '', validate=True)
    e, n, p, q = (number(doc, x) for x in ('Exponent', 'Modulus', 'P', 'Q'))
    if n != number(public, 'Modulus') or e != number(public, 'Exponent'):
        raise ValueError('Chave privada não corresponde à chave pública deste publicador.')
    bits = int.from_bytes(n, 'big').bit_length()
    if not 3072 <= bits <= 8192 or bits != len(n)*8 or int.from_bytes(e, 'big') != 65537 or not p or not q or int.from_bytes(p, 'big')*int.from_bytes(q, 'big') != int.from_bytes(n, 'big'):
        raise ValueError('Parâmetros da chave RSA inválidos.')
    return struct.pack('<6I', 0x32415352, bits, len(e), len(n), len(p), len(q))+e+n+p+q


def sign_blob(blob, message):
    api = c.WinDLL('bcrypt.dll')
    H, U, P = c.c_void_p, c.c_uint32, c.c_void_p
    declarations = {
        'BCryptOpenAlgorithmProvider': [c.POINTER(H), c.c_wchar_p, c.c_wchar_p, U],
        'BCryptImportKeyPair': [H, H, c.c_wchar_p, c.POINTER(H), P, U, U],
        'BCryptSignHash': [H, P, P, U, P, U, c.POINTER(U), U],
        'BCryptDestroyKey': [H], 'BCryptCloseAlgorithmProvider': [H, U]}
    for name, args in declarations.items():
        getattr(api, name).argtypes = args
        getattr(api, name).restype = c.c_int32
    class Padding(c.Structure):
        _fields_ = [('algorithm', c.c_wchar_p)]
    algorithm, key = H(), H()
    buffer = c.create_string_buffer(blob)
    try:
        if api.BCryptOpenAlgorithmProvider(c.byref(algorithm), 'RSA', None, 0) != 0:
            raise ValueError('Windows não iniciou o provedor RSA.')
        if api.BCryptImportKeyPair(algorithm, None, 'RSAPRIVATEBLOB', c.byref(key), buffer, len(blob), 0) != 0:
            raise ValueError('Windows recusou a chave privada RSA.')
        digest = hashlib.sha256(message).digest()
        hashed, padding, size = c.create_string_buffer(digest), Padding('SHA256'), U()
        if api.BCryptSignHash(key, c.byref(padding), hashed, len(digest), None, 0, c.byref(size), 2) != 0 or not 384 <= size.value <= 1024:
            raise ValueError('Windows não calculou o tamanho da assinatura.')
        result = c.create_string_buffer(size.value)
        if api.BCryptSignHash(key, c.byref(padding), hashed, len(digest), result, len(result), c.byref(size), 2) != 0:
            raise ValueError('Windows não conseguiu assinar o pacote.')
        return result.raw[:size.value]
    finally:
        c.memset(buffer, 0, len(buffer))
        if key.value:
            api.BCryptDestroyKey(key)
        if algorithm.value:
            api.BCryptCloseAlgorithmProvider(algorithm, 0)


def sign_message(message, public_path):
    if os.name != 'nt':
        raise ValueError('A assinatura nativa requer Windows.')
    path = Path(os.environ['LOCALAPPDATA'])/'EngelmigPublicacao/chave-privada.dpapi.xml'
    if not path.is_file():
        raise ValueError('Chave privada existente não encontrada nesta conta Windows.')
    try:
        xml = unprotect(encrypted_key(path))
        blob = private_blob(xml, public_path)
    except (ET.ParseError, UnicodeError):
        raise ValueError('Não foi possível ler a chave protegida existente.') from None
    finally:
        xml = None
    try:
        return sign_blob(blob, message)
    finally:
        blob = None
