#ifndef AppVersion
  #define AppVersion "3.0.0"
#endif

[Setup]
AppId=io.downtify.desktop
AppName=Downtify
AppVersion={#AppVersion}
DefaultDirName={autopf}\Downtify
DefaultGroupName=Downtify
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Downtify-Setup
SetupIconFile=..\frontend\public\favicon.ico
UninstallDisplayIcon={app}\Downtify.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Downtify\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\Downtify"; Filename: "{app}\Downtify.exe"
Name: "{autodesktop}\Downtify"; Filename: "{app}\Downtify.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Downtify.exe"; Description: "Launch Downtify"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(HKLM32,
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if WebView2Installed then Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'),
    '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := 'Could not start Microsoft WebView2 setup. Please retry.'
  else if not WebView2Installed then
    Result := 'Microsoft WebView2 could not be installed. Check your internet connection and retry. Setup exit code: ' + IntToStr(ExitCode);
end;
