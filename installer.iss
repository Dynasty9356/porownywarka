; Skrypt instalatora Inno Setup dla aplikacji FolderSync
; Zgodny ze standardami instalacji Windows 11

#define MyAppName "FolderSync"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "FolderSync Security Tools"
#define MyAppURL "https://github.com/Dynasty9356/porownywarka"
#define MyAppExeName "FolderSync.exe"

[Setup]
; Unikalny identyfikator GUID aplikacji (generowany dla FolderSync)
AppId={{9F2D851E-B4A1-4E7F-9A2C-5D48C17F7A8E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Plik ikony aplikacji dla instalatora
SetupIconFile=app_icon.ico
; Nowoczesny styl instalatora
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=output_installer
OutputBaseFilename=FolderSync_Setup_v{#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Build --onefile: jeden samodzielny plik .exe bez dodatkowych bibliotek
Source: "dist\FolderSync.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
