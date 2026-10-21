; Inno Setup 6. Per-user install; no admin privileges or registry permissions.
#define RepoRoot GetEnv('GARDEN_REPO_ROOT')
[Setup]
AppId={{DE48B9E8-8271-4F20-B2ED-76DFB759D422}
AppName=The Breathing Garden
AppVersion=1.1.1
AppPublisher=The Breathing Garden
AppPublisherURL=https://github.com/unravel-xu/yoga
DefaultDirName={localappdata}\Programs\BreathingGarden
DefaultGroupName=The Breathing Garden
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#RepoRoot}\dist
OutputBaseFilename=BreathingGarden-Windows-x64-Setup
SetupIconFile={#RepoRoot}\breathing_garden_app\assets\AppIcon.ico
UninstallDisplayIcon={app}\BreathingGarden.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "{#RepoRoot}\dist\BreathingGarden\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\The Breathing Garden"; Filename: "{app}\BreathingGarden.exe"
Name: "{userdesktop}\The Breathing Garden"; Filename: "{app}\BreathingGarden.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\BreathingGarden.exe"; Description: "Launch The Breathing Garden"; Flags: nowait postinstall skipifsilent
