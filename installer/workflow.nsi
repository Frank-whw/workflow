!include "MUI2.nsh"

!ifdef PROJ_ROOT
!else
!define PROJ_ROOT "${__FILEDIR__}\\.."
!endif

Name "Workflow"
OutFile "${PROJ_ROOT}\\dist\\workflow-setup.exe"
InstallDir "$PROGRAMFILES64\\Workflow"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"
  File "${PROJ_ROOT}\\dist\\workflow-web.exe"
  File "${PROJ_ROOT}\\dist\\workflow-worker.exe"
  File "${PROJ_ROOT}\\scripts\\start_all.bat"
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\\Workflow"
  CreateDirectory "$LOCALAPPDATA\\Workflow"
  CreateShortCut "$SMPROGRAMS\\Workflow\\Start Web.lnk" "$INSTDIR\\workflow-web.exe" "" "$INSTDIR\\workflow-web.exe" 0 "" "" "$LOCALAPPDATA\\Workflow"
  CreateShortCut "$SMPROGRAMS\\Workflow\\Start Worker.lnk" "$INSTDIR\\workflow-worker.exe" "" "$INSTDIR\\workflow-worker.exe" 0 "" "" "$LOCALAPPDATA\\Workflow"
  CreateShortCut "$SMPROGRAMS\\Workflow\\Start All.lnk" "$INSTDIR\\start_all.bat" "" "$INSTDIR\\workflow-web.exe" 0 "" "" "$LOCALAPPDATA\\Workflow"
  CreateShortCut "$SMPROGRAMS\\Workflow\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"
  CreateShortCut "$DESKTOP\\Workflow Start.lnk" "$INSTDIR\\start_all.bat" "" "$INSTDIR\\workflow-web.exe" 0 "" "" "$LOCALAPPDATA\\Workflow"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\\Workflow\\Start Web.lnk"
  Delete "$SMPROGRAMS\\Workflow\\Start Worker.lnk"
  Delete "$SMPROGRAMS\\Workflow\\Start All.lnk"
  Delete "$SMPROGRAMS\\Workflow\\Uninstall.lnk"
  RMDir "$SMPROGRAMS\\Workflow"
  Delete "$DESKTOP\\Workflow Start.lnk"
  Delete "$INSTDIR\\workflow-web.exe"
  Delete "$INSTDIR\\workflow-worker.exe"
  Delete "$INSTDIR\\start_all.bat"
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd