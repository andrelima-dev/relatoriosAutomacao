; Instalador do Gerador de Relatorios OAB
; Compilar com: create_installer.bat  (ou ISCC.exe installer.iss)

; GUID que identifica a instalacao entre versoes. NAO alterar: e por ele que o
; instalador reconhece (e remove) as versoes ja instaladas.
#define MyAppId "{8F3A6C21-4D7B-4E92-9C15-2A0B7E5D3F84}"
#define MyAppName "Gerador de Relatorios OAB"
#define MyAppVersion "2.4"
#define MyAppPublisher "andrelima-dev"
#define MyAppExe "Gerador_OAB.exe"

[Setup]
AppId={{#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\Gerador OAB
DefaultGroupName=Gerador OAB
OutputDir=installer_output
OutputBaseFilename=Gerador_OAB_Setup
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardImageFile=assets\wizard.bmp,assets\wizard@2x.bmp
WizardSmallImageFile=assets\wizard_small.bmp,assets\wizard_small@2x.bmp
; Instala para o usuario atual (sem UAC), mas permite escolher "todos" se quiser
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Fecha o app se estiver aberto, em vez de falhar com arquivo em uso
CloseApplications=yes
RestartApplications=no
MinVersion=6.1sp1
DisableProgramGroupPage=yes
ShowLanguageDialog=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
brazilianportuguese.WelcomeLabel2=Este assistente vai instalar o [name/ver] no seu computador.%n%nSe ja houver uma versao instalada, ela sera removida automaticamente antes da instalacao da nova.%n%nFeche o Gerador de Relatorios OAB antes de continuar.

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Icones adicionais:"
Name: "quicklaunch"; Description: "Fixar na Barra de Tarefas (atalho rapido)"; GroupDescription: "Icones adicionais:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{userprograms}\Desinstalar Gerador OAB"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; Comment: "Gerador de Relatorios OAB"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: quicklaunch

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Iniciar o {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Restos do PyInstaller/logs que possam sobrar na pasta
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"

[Code]
const
  { AppId das versoes antigas: sem AppId definido, o Inno usava o AppName }
  LegacyAppId = 'Gerador de Relatorios OAB';

var
  VersaoAnterior: String;

{ Procura a instalacao em HKCU, HKLM 32 e HKLM 64 bits }
function AcharInstalacao(const AppIdent: String; var UninstCmd: String;
  var Versao: String): Boolean;
var
  Chave: String;
  Raizes: array[0..2] of Integer;
  i: Integer;
begin
  Result := False;
  UninstCmd := '';
  Versao := '';
  Chave := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + AppIdent + '_is1';
  Raizes[0] := HKEY_CURRENT_USER;
  Raizes[1] := HKEY_LOCAL_MACHINE;
  Raizes[2] := HKEY_LOCAL_MACHINE_64;
  for i := 0 to 2 do
  begin
    if RegQueryStringValue(Raizes[i], Chave, 'UninstallString', UninstCmd) and
       (UninstCmd <> '') then
    begin
      RegQueryStringValue(Raizes[i], Chave, 'DisplayVersion', Versao);
      Result := True;
      Exit;
    end;
  end;
end;

function AcharQualquerInstalacao(var UninstCmd: String; var Versao: String): Boolean;
begin
  { Chave literal: SetupSetting('AppId') devolveria o valor do script, com a
    chave dupla de escape, que nao casa com a chave real do registro. }
  Result := AcharInstalacao('{#MyAppId}', UninstCmd, Versao);
  if not Result then
    Result := AcharInstalacao(LegacyAppId, UninstCmd, Versao);
end;

{ Roda o desinstalador da versao antiga em modo silencioso }
function RemoverVersaoAnterior(const UninstCmd: String): Boolean;
var
  Cmd, Params: String;
  Codigo: Integer;
begin
  Cmd := RemoveQuotes(UninstCmd);
  Params := '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART';
  Result := Exec(Cmd, Params, '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  if Result then
    Result := (Codigo = 0);
  { O desinstalador do Inno se copia para o temp e retorna antes de terminar;
    espera a pasta ser liberada para nao apagar os arquivos novos por engano }
  if Result then
    Sleep(2000);
end;

function InitializeSetup(): Boolean;
var
  UninstCmd: String;
begin
  Result := True;
  VersaoAnterior := '';
  if AcharQualquerInstalacao(UninstCmd, VersaoAnterior) then
  begin
    if VersaoAnterior = '' then
      VersaoAnterior := '(desconhecida)';
    if CompareText(VersaoAnterior, '{#MyAppVersion}') = 0 then
    begin
      if MsgBox('A versao ' + VersaoAnterior + ' ja esta instalada neste computador.'#13#10#13#10 +
                'Deseja reinstalar?', mbConfirmation, MB_YESNO) = IDNO then
        Result := False;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  UninstCmd, Versao: String;
begin
  Result := '';
  NeedsRestart := False;
  if AcharQualquerInstalacao(UninstCmd, Versao) then
  begin
    WizardForm.StatusLabel.Caption := 'Removendo a versao anterior (' + Versao + ')...';
    WizardForm.Refresh();
    if not RemoverVersaoAnterior(UninstCmd) then
      Result := 'Nao foi possivel remover a versao ' + Versao + ' instalada.'#13#10#13#10 +
                'Desinstale manualmente em Configuracoes > Aplicativos e execute este ' +
                'instalador novamente.';
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpReady) and (VersaoAnterior <> '') then
    WizardForm.ReadyMemo.Lines.Insert(0,
      'A versao ' + VersaoAnterior + ' sera removida antes da instalacao.' + #13#10);
end;
