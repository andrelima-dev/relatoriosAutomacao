[Setup]
AppName=Gerador de Relatorios OAB
AppVersion=1.0
AppPublisher=OAB
DefaultDirName={autopf}\Gerador OAB
DefaultGroupName=Gerador OAB
OutputDir=installer_output
OutputBaseFilename=Gerador_OAB_Setup
SetupIconFile=assets\logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Icones adicionais:"

[Files]
Source: "dist\Gerador_OAB.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Gerador de Relatorios OAB"; Filename: "{app}\Gerador_OAB.exe"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Gerador de Relatorios OAB"; Filename: "{app}\Gerador_OAB.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Gerador_OAB.exe"; Description: "Iniciar Gerador de Relatorios OAB"; Flags: nowait postinstall skipifsilent
