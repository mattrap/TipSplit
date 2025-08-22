; installer.iss  (checked into your repo)
#define MyAppName "TipSplit"
#define MyAppExeName "TipSplit.exe"

; MyAppVersion will be injected from the CI command line.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
OutputDir=dist\installer
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\TipSplit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent
