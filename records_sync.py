"""Sincronização de registros imutáveis em uma branch exclusiva do repositório.

Usa um repositório Git bare dentro de dados; não troca a branch do programa.
Pushes são sempre fast-forward. Em concorrência, refaz a união sobre o novo
commit remoto. Credenciais são obtidas pelo Git instalado no computador.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone

EVENT_PATH = re.compile(r'^registros/([a-f0-9]{2})/([a-f0-9]{64})\.json$')
MAX_EVENT = 1_000_000
MAX_EVENTS = 100000


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class SyncError(Exception):
    pass


class RecordSync:
    def __init__(self, folder, settings, export_events, import_events):
        self.folder=Path(folder)/'sincronizacao'
        self.settings=settings
        self.export_events=export_events
        self.import_events=import_events
        self.lock=threading.Lock()
        self.wake=threading.Event()
        self.stopping=threading.Event()
        self.thread=None
        self.state={'running':False,'last_success':None,'error':'','pending':None,'uploaded':0,'downloaded':0,'configuration':None}
        try:
            saved=json.loads((self.folder/'estado.json').read_text(encoding='utf-8'))
            self.state.update({k:saved[k] for k in self.state if k in saved})
        except (OSError,ValueError):
            pass
        self.state['running']=False

    def status(self):
        conf=self.settings()
        state=dict(self.state)
        if state.get('configuration')!=[conf['repository'],conf.get('sync_branch','registros-materiais')]:
            state.update(error='',last_success=None,pending=None,uploaded=0,downloaded=0)
        return {**state,'enabled':bool(conf.get('sync_enabled',True)),
                'repository':conf['repository'],'branch':conf.get('sync_branch','registros-materiais'),'interval_seconds':60}

    def save_state(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        path=self.folder/'estado.json';temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state,ensure_ascii=False),encoding='utf-8');os.replace(temp,path)

    def git(self, cache, *args, content=None, extra_env=None, check=True):
        env=os.environ.copy()
        for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE'):env.pop(key,None)
        env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',
                   GIT_AUTHOR_NAME='Fechamento Engelmig',GIT_COMMITTER_NAME='Fechamento Engelmig',
                   GIT_AUTHOR_EMAIL='registros@localhost',GIT_COMMITTER_EMAIL='registros@localhost')
        env.update(extra_env or {})
        command=['git','-c','core.hooksPath='+str(self.folder/'sem-hooks'),'-c','commit.gpgSign=false','-c','gc.auto=0']
        if cache:command+=['--git-dir='+str(cache)]
        try:
            result=subprocess.run(command+list(args),input=content,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=env,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except FileNotFoundError:
            raise SyncError('Git não encontrado. Instale o Git e configure uma conta com acesso ao repositório.')
        except subprocess.TimeoutExpired:
            raise SyncError('A conexão com o repositório demorou demais. Os registros continuam salvos e serão reenviados.')
        if check and result.returncode:
            detail=result.stderr.decode('utf-8','replace').strip()[-900:]
            raise SyncError(self.connection_error(detail))
        return result

    @staticmethod
    def connection_error(detail):
        lower=detail.lower()
        if any(word in lower for word in ('repository not found','authentication failed','could not read username','terminal prompts disabled')):
            return 'O Git não conseguiu acessar o repositório com a conta deste computador. Confira o endereço e autentique uma conta com acesso. Testar acesso ao repositório verifica a leitura pública; salvar o link não conecta a conta Git.'
        if any(word in lower for word in ('permission denied','write access','403','permission to','access denied')):
            return 'A conta configurada no Git não tem permissão para enviar registros a este repositório. Configure uma conta com permissão de escrita. Os registros continuam salvos neste computador.'
        if any(word in lower for word in ('could not resolve','failed to connect','unable to access','ssl certificate','timed out')):
            return 'O Git não conseguiu conectar ao GitHub. Confira a internet, o proxy e o certificado da rede da empresa. Os registros continuam salvos neste computador.'
        return 'Não foi possível sincronizar os registros. Confira a conexão e a conta configurada no Git. '+detail[-500:]

    def remote_tree(self,cache,branch):
        ref='refs/heads/'+branch
        probe=self.git(cache,'ls-remote','--exit-code','origin',ref,check=False)
        if probe.returncode==2:return None,{}
        if probe.returncode:
            raise SyncError(self.connection_error(probe.stderr.decode('utf-8','replace')))
        self.git(cache,'fetch','--no-tags','origin',ref)
        tip=self.git(cache,'rev-parse','FETCH_HEAD').stdout.decode().strip()
        tree=self.git(cache,'ls-tree','-rlz',tip).stdout
        files={}
        for item in tree.split(b'\0'):
            if not item:continue
            header,path=item.split(b'\t',1)
            name=path.decode('utf-8','replace');match=EVENT_PATH.fullmatch(name)
            if not match:continue
            mode,kind,oid,size=header.split()
            if mode!=b'100644' or kind!=b'blob' or int(size)>MAX_EVENT or match[1]!=match[2][:2]:
                raise SyncError('Arquivo de registro inválido no repositório: '+name)
            files[match[2]]=(name,oid.decode(),int(size))
        if len(files)>MAX_EVENTS:raise SyncError('A base ultrapassou 100.000 registros. Divida ou arquive a base antes de continuar.')
        return tip,files

    def read_events(self,cache,files):
        if not files:return []
        raw=self.git(cache,'cat-file','--batch',content=('\n'.join(oid for _,oid,_ in files)+'\n').encode()).stdout
        events=[];pos=0
        for name,oid,size in files:
            end=raw.index(b'\n',pos);header=raw[pos:end].split();pos=end+1
            if header!=[oid.encode(),b'blob',str(size).encode()]:raise SyncError('Objeto Git de registro inconsistente.')
            event=json.loads(raw[pos:pos+size].decode('utf-8'));pos+=size+1
            if not isinstance(event,dict) or event.get('id')!=EVENT_PATH.fullmatch(name)[2]:raise SyncError('Identificador de registro divergente no repositório.')
            events.append(event)
        return events

    def union_commit(self,cache,tip,events):
        index=cache/'indice-sincronizacao'
        if index.exists():index.unlink()
        env={'GIT_INDEX_FILE':str(index)}
        self.git(cache,'read-tree',tip or '--empty',extra_env=env)
        updates=[]
        for event in events:
            binary=json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
            if len(binary)>MAX_EVENT:raise SyncError('Um registro ultrapassa o limite de 1 MB; ele permanece salvo localmente.')
            oid=self.git(cache,'hash-object','-w','--stdin',content=binary).stdout.decode().strip()
            ident=event['id'];updates.append(f'100644 {oid}\tregistros/{ident[:2]}/{ident}.json\0')
        if not tip:
            note=b'Registros de composicoes do Fechamento Engelmig. Cada JSON representa um salvamento, inclusive repetido.\n'
            oid=self.git(cache,'hash-object','-w','--stdin',content=note).stdout.decode().strip()
            updates.append(f'100644 {oid}\tREADME.txt\0')
        self.git(cache,'update-index','-z','--index-info',content=''.join(updates).encode(),extra_env=env)
        tree=self.git(cache,'write-tree',extra_env=env).stdout.decode().strip()
        parent=['-p',tip] if tip else []
        commit=self.git(cache,'commit-tree',tree,*parent,content=f'Reunir {len(events)} registro(s) de composicoes\n'.encode()).stdout.decode().strip()
        # Mantém o commit local em caso de queda de energia ou falha de rede.
        self.git(cache,'update-ref','refs/heads/fila-local',commit)
        return commit

    def sync_once(self):
        if not self.lock.acquire(blocking=False):return self.status()
        try:
            conf=self.settings()
            if not conf.get('sync_enabled',True):return self.status()
            branch=conf.get('sync_branch','registros-materiais')
            if self.state.get('configuration')!=[conf['repository'],branch]:
                self.state.update(configuration=[conf['repository'],branch],last_success=None,error='',pending=None,uploaded=0,downloaded=0)
            if branch==conf.get('branch','main') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]*',branch) or '..' in branch or '//' in branch or branch.endswith('/'):
                raise SyncError('Use uma branch exclusiva de registros, diferente da branch do programa.')
            self.state.update(running=True,error='',last_attempt=stamp(),uploaded=0,downloaded=0,pending=None,configuration=[conf['repository'],branch])
            self.folder.mkdir(parents=True,exist_ok=True)
            key=hashlib.sha256((conf['repository']+'|'+branch).encode()).hexdigest()[:20]
            cache=self.folder/(key+'.git')
            if not cache.exists():
                self.git(None,'init','--bare',str(cache))
                self.git(cache,'remote','add','origin',conf['repository'])
            local={e['id']:e for e in self.export_events()}
            downloaded=0
            for attempt in range(4):
                tip,remote=self.remote_tree(cache,branch)
                unknown=[entry for ident,entry in remote.items() if ident not in local]
                for start in range(0,len(unknown),100):
                    events=self.read_events(cache,unknown[start:start+100])
                    self.import_events(events)
                    local.update((e['id'],e) for e in events);downloaded+=len(events)
                outgoing=[event for ident,event in local.items() if ident not in remote]
                self.state.update(pending=len(outgoing),downloaded=downloaded)
                if not outgoing:break
                commit=self.union_commit(cache,tip,outgoing)
                pushed=self.git(cache,'push','origin',commit+':refs/heads/'+branch,check=False)
                if pushed.returncode==0:
                    self.state.update(uploaded=len(outgoing),pending=0);break
                detail=pushed.stderr.decode('utf-8','replace')
                if not any(code in detail for code in ('fetch first','non-fast-forward','failed to update ref','cannot lock ref')):
                    raise SyncError('Recebimento concluído; envio pendente. '+self.connection_error(detail))
                if attempt==3:raise SyncError('Outros computadores estão enviando registros. A próxima tentativa continuará sem sobrescrever o histórico.')
            self.state.update(last_success=stamp(),error='')
        except (SyncError,OSError,ValueError,KeyError) as exc:
            self.state['error']=str(exc)
        except Exception:
            self.state['error']='Não foi possível concluir a sincronização. Os registros permanecem locais; haverá nova tentativa automática.'
        finally:
            self.state['running']=False
            try:self.save_state()
            except OSError:self.state['error']='Histórico preservado; não foi possível gravar o estado da sincronização.'
            self.lock.release()
        return self.status()

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stopping.clear()
        def worker():
            while not self.stopping.is_set():
                self.sync_once()
                self.wake.wait(60);self.wake.clear()
        self.thread=threading.Thread(target=worker,daemon=True,name='engelmig-registros')
        self.thread.start()

    def trigger(self):
        if self.thread and self.thread.is_alive():self.wake.set()
        else:self.start()
        return self.status()

    def stop(self):
        self.stopping.set();self.wake.set()
