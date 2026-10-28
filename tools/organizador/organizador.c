#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#define CAP 32768
#define COUNT(a) (sizeof(a)/sizeof((a)[0]))
typedef struct { const wchar_t *from, *to; int selected, moved; } Item;
static Item items[] = {
 {L"ATUALIZAR.txt", L"docs\\historico\\ATUALIZAR.txt",0,0},
 {L"PUBLICAR_RELEASE.txt", L"docs\\historico\\PUBLICAR_RELEASE.txt",0,0},
 {L"LEIA-ME.txt", L"docs\\historico\\LEIA-ME.txt",0,0},
 {L"GIT.txt", L"docs\\GIT.txt",0,0},
 {L"SEGURANCA_PREPARACAO.md", L"docs\\SEGURANCA_PREPARACAO.md",0,0},
 {L"CRIAR_CHAVE_PUBLICACAO.bat", L"tools\\publicacao\\CRIAR_CHAVE_PUBLICACAO.bat",0,0},
 {L"assinatura-atualizacao.ps1", L"tools\\publicacao\\assinatura-atualizacao.ps1",0,0}
};
static wchar_t root[CAP], backup[CAP];
static void pause_exit(void) { wchar_t line[32]; wprintf(L"\nPressione Enter para fechar.\n"); fgetws(line,32,stdin); }
static int join(wchar_t *out, const wchar_t *base, const wchar_t *rel) {
 if(wcslen(base)+wcslen(rel)+2>=CAP) return 0;
 swprintf(out,CAP,L"%ls\\%ls",base,rel); return 1;
}
static int isfile(const wchar_t *p) {
 DWORD a=GetFileAttributesW(p);
 return a!=INVALID_FILE_ATTRIBUTES && !(a&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT));
}
/* Reject junctions/symlinks throughout the selected project and destinations. */
static int safe_path(const wchar_t *p) {
 wchar_t part[CAP]; size_t n=wcslen(p); if(n>=CAP) return 0;
 wcscpy(part,p);
 for(size_t i=3;i<=n;i++) if(part[i]==L'\\'||part[i]==0) {
  wchar_t c=part[i]; part[i]=0; DWORD a=GetFileAttributesW(part);
  if(a!=INVALID_FILE_ATTRIBUTES && (a&FILE_ATTRIBUTE_REPARSE_POINT)) return 0;
  part[i]=c;
 }
 return 1;
}
static int parents(const wchar_t *p) {
 wchar_t part[CAP]; wcscpy(part,p);
 for(size_t i=3;part[i];i++) if(part[i]==L'\\') {
  part[i]=0;
  if(!CreateDirectoryW(part,NULL) && GetLastError()!=ERROR_ALREADY_EXISTS) return 0;
  DWORD a=GetFileAttributesW(part);
  if(a==INVALID_FILE_ATTRIBUTES || !(a&FILE_ATTRIBUTE_DIRECTORY) || (a&FILE_ATTRIBUTE_REPARSE_POINT))return 0;
  part[i]=L'\\';
 }
 return 1;
}
static int matches(const wchar_t *a,const wchar_t *b) {
 HANDLE x=CreateFileW(a,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 HANDLE y=CreateFileW(b,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 int ok=0; unsigned char bx[65536],by[65536]; DWORD nx,ny;
 if(x==INVALID_HANDLE_VALUE||y==INVALID_HANDLE_VALUE)goto done;
 for(;;){ if(!ReadFile(x,bx,sizeof bx,&nx,NULL)||!ReadFile(y,by,sizeof by,&ny,NULL)||nx!=ny)goto done;
  if(!nx){ok=1;break;} if(memcmp(bx,by,nx))goto done; }
done: if(x!=INVALID_HANDLE_VALUE)CloseHandle(x);if(y!=INVALID_HANDLE_VALUE)CloseHandle(y);return ok;
}
static int candidate(const wchar_t *folder) {
 wchar_t p[CAP]; return join(p,folder,L"app.py")&&isfile(p)&&join(p,folder,L"version.json")&&isfile(p)&&join(p,folder,L"INICIAR.bat")&&isfile(p);
}
int wmain(int argc,wchar_t **argv) {
 wchar_t p[CAP],q[CAP],saved[CAP],input[CAP]; unsigned selected=0;
 SetConsoleOutputCP(CP_UTF8);
 wprintf(L"ENGELMIG - ORGANIZADOR DO PROJETO\n\nNao instala programas, nao usa PowerShell e nao acessa a internet.\nFeche o aplicativo antes de continuar.\n");
 if(argc>1){if(!GetFullPathNameW(argv[1],CAP,root,NULL))goto invalid;}
 else {
  GetModuleFileNameW(NULL,root,CAP); wchar_t *slash=wcsrchr(root,L'\\');if(slash)*slash=0;
  if(!candidate(root)){GetCurrentDirectoryW(CAP,root);}
  if(!candidate(root)){
   wprintf(L"Cole o caminho da pasta que contem app.py e INICIAR.bat:\n");
   if(!fgetws(input,CAP,stdin))return 1;
   input[wcscspn(input,L"\r\n")]=0;
   size_t len=wcslen(input); wchar_t *value=input;
   if(len>=2 && input[0]==L'"' && input[len-1]==L'"'){input[len-1]=0;value++;}
   if(!GetFullPathNameW(value,CAP,root,NULL))goto invalid;
  }
 }
 while(wcslen(root)>3 && root[wcslen(root)-1]==L'\\')root[wcslen(root)-1]=0;
 if(!candidate(root)||!safe_path(root)||wcslen(root)>20000||root[1]!=L':')goto invalid;
 wprintf(L"\nProjeto: %ls\n\nMovimentacoes previstas:\n",root);
 for(unsigned i=0;i<COUNT(items);i++){
  join(p,root,items[i].from);join(q,root,items[i].to);
  if(!isfile(p))continue;
  if(!safe_path(p)||!safe_path(q)){wprintf(L"Caminho com link recusado: %ls\n",p);goto failed;}
  if(GetFileAttributesW(q)!=INVALID_FILE_ATTRIBUTES){wprintf(L"PRESERVADO (destino ja existe): %ls\n",items[i].from);continue;}
  items[i].selected=1;selected++;wprintf(L"  %ls -> %ls\n",items[i].from,items[i].to);
 }
 /* Keep the launcher and its adjacent script together. */
 if(items[5].selected!=items[6].selected){
  selected-=items[5].selected+items[6].selected;items[5].selected=items[6].selected=0;
  wprintf(L"Ferramentas de assinatura preservadas: o par precisa estar completo e livre de conflitos.\n");
 }
 if(!selected){wprintf(L"\nNada a mover. A estrutura ja esta organizada ou ha destinos existentes.\n");pause_exit();return 0;}
 wprintf(L"\nDados, fotos, croquis, planilhas, bibliotecas, testes, chaves e modulos Python serao preservados.\nNenhum arquivo sera excluido.\nConfirme que o programa esta FECHADO. Digite ORGANIZAR para continuar:\n");
 if(!fgetws(input,CAP,stdin))return 1;input[wcscspn(input,L"\r\n")]=0;
 if(wcscmp(input,L"ORGANIZAR")){wprintf(L"Cancelado. Nenhum arquivo foi movido.\n");pause_exit();return 0;}
 SYSTEMTIME t;GetLocalTime(&t);
 swprintf(backup,CAP,L"%ls_backup_organizacao_%04u%02u%02u_%02u%02u%02u_%lu",root,t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,GetCurrentProcessId());
 if(!safe_path(backup)||!CreateDirectoryW(backup,NULL)){wprintf(L"Nao foi possivel criar backup ao lado do projeto. Erro %lu.\n",GetLastError());goto failed;}
 /* Copy and compare every source BEFORE the first move. */
 for(unsigned i=0;i<COUNT(items);i++)if(items[i].selected){
  join(p,root,items[i].from);join(saved,backup,items[i].from);
  if(!safe_path(p)||!CopyFileW(p,saved,TRUE)||!matches(p,saved)){wprintf(L"Backup nao confirmado. Nada foi movido.\n");goto failed;}
 }
 join(p,backup,L"RESTAURAR.txt");
 HANDLE log=CreateFileW(p,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
 if(log==INVALID_HANDLE_VALUE)goto failed;
 DWORD written; const char *note="BACKUP ANTES DA ORGANIZACAO\r\nFeche o aplicativo. Para restaurar, copie os arquivos desta pasta para a raiz original do projeto. Confira antes de substituir arquivos editados posteriormente. Os arquivos organizados em docs/ e tools/publicacao/ sao copias correspondentes; nao apague documentos personalizados.\r\n";
 if(!WriteFile(log,note,(DWORD)strlen(note),&written,NULL)){CloseHandle(log);goto failed;}CloseHandle(log);
 for(unsigned i=0;i<COUNT(items);i++)if(items[i].selected){
  join(p,root,items[i].from);join(q,root,items[i].to);join(saved,backup,items[i].from);
  if(!safe_path(p)||!safe_path(q)||!matches(p,saved)||!parents(q)||!MoveFileW(p,q)){
   wprintf(L"Falha ao mover %ls. Restaurando movimentacoes anteriores.\n",items[i].from);
   for(int j=(int)i-1;j>=0;j--)if(items[j].moved){join(p,root,items[j].from);join(q,root,items[j].to);
    if(!MoveFileW(q,p))wprintf(L"Restauracao manual necessaria: %ls\n",items[j].from);}
   wprintf(L"Backup preservado: %ls\n",backup);goto failed;
  }
  items[i].moved=1;
 }
 wprintf(L"\nOrganizacao concluida.\nBackup: %ls\n\nInicie normalmente por VERIFICAR_E_INICIAR.bat ou INICIAR.bat.\nOs modulos internos permanecem na raiz para compatibilidade.\n",backup);
 pause_exit();return 0;
invalid: wprintf(L"Pasta invalida. Escolha uma pasta local de projeto, sem links, contendo app.py, version.json e INICIAR.bat.\n");
failed: wprintf(L"Operacao interrompida. Nenhum arquivo foi excluido.\n");pause_exit();return 1;
}
