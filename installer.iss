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
; PyInstaller build output (folder tree)
Source: "dist\TipSplit\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; Ensure icon asset is available for shortcuts
Source: "assets\icons\app_icon.ico"; DestDir: "{app}\assets\icons"; Flags: ignoreversion

; Ship read-only defaults alongside the app (single files → no createallsubdirs needed)
Source: "defaults\service_employees.json"; DestDir: "{app}\defaults"; Flags: ignoreversion
Source: "defaults\bussboy_employees.json";  DestDir: "{app}\defaults"; Flags: ignoreversion

; Seed the user-writable backend on first install only (single files)
Source: "defaults\service_employees.json"; DestDir: "{userappdata}\TipSplit\backend"; Flags: onlyifdoesntexist ignoreversion
Source: "defaults\bussboy_employees.json";  DestDir: "{userappdata}\TipSplit\backend"; Flags: onlyifdoesntexist ignoreversion

[InstallDelete]
; Clean up legacy misplaced files if they exist
Type: files; Name: "{app}\service_employees.json"
Type: files; Name: "{app}\bussboy_employees.json"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\app_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icons\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
