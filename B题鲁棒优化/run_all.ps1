$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
function Native([string]$Program,[string[]]$Parameters){& $Program @Parameters;if($LASTEXITCODE -ne 0){throw "Failed $Program $LASTEXITCODE"}}
Native 'g++' @('-std=c++17','-O3','tests/test_certified_route.cpp','-o','tests/test_certified_route.exe')
Native './tests/test_certified_route.exe' @()
Native 'g++' @('-std=c++17','-O3','tests/test_uncertain_position.cpp','-o','tests/test_uncertain_position.exe')
Native './tests/test_uncertain_position.exe' @()
Native 'g++' @('-std=c++17','-O3','src/ablation.cpp','-o','ablation.exe')
Native 'g++' @('-std=c++17','-O3','src/stratified.cpp','-o','stratified.exe')
Native 'g++' @('-std=c++17','-O3','src/hardware_check.cpp','-o','hardware_check.exe')
Native 'g++' @('-std=c++17','-O3','src/robot.cpp','-o','robot.exe')
Native 'python' @('review/q4_area_arc_certificate.py','review/q4_area_arc_certificate.json')
Native 'python' @('review/independent_robust_replay.py','review/cover21_eta0.4_r999.6.json')
Native './ablation.exe' @('results/iid.csv','510001','200')
Native './stratified.exe' @('results/stratified.csv')
Native './hardware_check.exe' @('results/hardware.csv')
Native 'python' @('review/test_bridge_deadline.py')
Native 'python' @('src/validate_mock.py','--count','30')
Native 'python' @('src/analyze_round4.py')
Native 'python' @('src/compose_round4.py')
Write-Output 'Fourth round numerical pipeline completed.'
