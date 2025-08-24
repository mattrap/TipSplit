; --- installer.iss ---

#define MyAppName "TipSplit"
#define MyAppExeName "TipSplit.exe"
; If CI passes /DMyAppVersion=..., it's defined; otherwise default locally:
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Mathias Tessier"

[Setup]
AppId={{6C7B8BF8-CE9D-4C6D-A3C0-6E3D6BEF44E3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
; Your icon lives here:
SetupIconFile=assets\icons\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french";  MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; PyInstaller build output
Source: "dist\TipSplit\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; Ship read-only defaults alongside the app
Source: "defaults\service_employees.json"; DestDir: "{app}\defaults"; Flags: ignoreversion createallsubdirs
Source: "defaults\bussboy_employees.json"; DestDir: "{app}\defaults"; Flags: ignoreversion createallsubdirs

; Seed the user-writable backend (first install only)
Source: "defaults\service_employees.json"; DestDir: "{userappdata}\TipSplit\backend"; Flags: onlyifdoesntexist ignoreversion createallsubdirs
Source: "defaults\bussboy_employees.json"; DestDir: "{userappdata}\TipSplit\backend"; Flags: onlyifdoesntexist ignoreversion createallsubdirs

[InstallDelete]
; Clean up legacy misplaced files if they exist
Type: files; Name: "{app}\service_employees.json"
Type: files; Name: "{app}\bussboy_employees.json"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
