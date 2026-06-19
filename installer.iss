; ============================================================
; RePKG-GUI Inno Setup 6 安装脚本
;
; 编译: ISCC.exe installer.iss  (Inno Setup >= 6.0)
; ============================================================

#define AppName "RePKG-GUI"
#define AppVersion "1.0.1"
#define AppPublisher "RePKG-GUI Team"
#define AppURL "https://github.com/RePKG-GUI"
#define AppExeName "RePKG-GUI.exe"
#define SourcePath "dist\" + AppName

[Setup]
AppId={{B6F2A8D4-3C7E-4F1A-9D2E-6A8B5C0D3E7F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf64}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=static\assets\images\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\static\assets\images\icon.ico
UninstallDisplayName={#AppName} {#AppVersion}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式:"

[Files]
; ---- 主程序 ----
Source: "{#SourcePath}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; ---- 配置文件（首次安装写入，升级/覆盖安装不覆盖已有） ----
Source: "{#SourcePath}\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; ---- 模板文件 ----
Source: "{#SourcePath}\templates\base.html";     DestDir: "{app}\templates"; Flags: ignoreversion
Source: "{#SourcePath}\templates\index.html";    DestDir: "{app}\templates"; Flags: ignoreversion
Source: "{#SourcePath}\templates\settings.html"; DestDir: "{app}\templates"; Flags: ignoreversion

; ---- 静态资源 ----
Source: "{#SourcePath}\static\css\custom.css"; DestDir: "{app}\static\css"; Flags: ignoreversion
Source: "{#SourcePath}\static\js\app.js";       DestDir: "{app}\static\js";  Flags: ignoreversion

; ---- 资源文件 ----
Source: "{#SourcePath}\static\assets\RePKG.exe";                        DestDir: "{app}\static\assets";         Flags: ignoreversion
Source: "{#SourcePath}\static\assets\images\icon.ico";                  DestDir: "{app}\static\assets\images"; Flags: ignoreversion
Source: "{#SourcePath}\static\assets\images\background\*";              DestDir: "{app}\static\assets\images\background"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// 安装前检查已有安装
function InitializeSetup: Boolean;
var
  UninstPath: string;
  ResultCode: Integer;
begin
  Result := True;
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}_is1',
    'UninstallString', UninstPath) then
  begin
    if MsgBox('检测到 {#AppName} 已安装。' + #13#10#13#10 +
              '点击"是"将先卸载旧版本（保留用户数据），然后继续安装。' + #13#10 +
              '点击"否"取消安装。', mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(RemoveQuotes(UninstPath), '/VERYSILENT /NORESTART', '', SW_SHOW,
        ewWaitUntilTerminated, ResultCode);
    end
    else
      Result := False;
  end;
end;

// 卸载前备份用户数据到临时目录，卸载后恢复
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigBak: string;
begin
  ConfigBak := ExpandConstant('{tmp}\RePKG-GUI-config.json');

  if CurUninstallStep = usUninstall then
  begin
    // 备份用户配置到临时目录
    if FileExists(ExpandConstant('{app}\config.json')) then
      FileCopy(ExpandConstant('{app}\config.json'), ConfigBak, False);
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    if FileExists(ConfigBak) then
    begin
      CreateDir(ExpandConstant('{app}'));
      RenameFile(ConfigBak, ExpandConstant('{app}\config.json'));
    end;
  end;
end;
