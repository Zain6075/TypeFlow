; ---------------------------------------------------------------------------
;  TypeFlow - Windows installer (Inno Setup 6)
;
;  Build it together with the portable .exe:
;     pyinstaller ... run.py                 (produces dist\TypeFlow.exe)
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\TypeFlow.iss
;
;  Or let GitHub Actions do it: .github/workflows/build-windows.yml
;  The version can be overridden on the command line:  /DMyAppVersion=1.2.3
; ---------------------------------------------------------------------------
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "TypeFlow"
#define MyAppNameAndVersion MyAppName + " " + MyAppVersion
#define MyAppPublisher "TypeFlow contributors"
#define MyAppURL "https://github.com/Zain6075/TypeFlow"
#define MyAppExeName "TypeFlow.exe"

; Path of the PyInstaller output (override with /DTypeFlowExe=... if needed).
#ifndef TypeFlowExe
  #define TypeFlowExe "..\dist\TypeFlow.exe"
#endif

[Setup]
; A stable AppId keeps upgrades in place (do not change between releases).
AppId={{7E9B2C4A-1F3D-4B8E-9A5C-TYPEFLOW0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameAndVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
; Per-user install into %LOCALAPPDATA%\Programs - no UAC prompt needed.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=TypeFlowSetup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppNameAndVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The single-file PyInstaller build - everything is inside this .exe.
Source: "{#TypeFlowExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app once the install finishes.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent
