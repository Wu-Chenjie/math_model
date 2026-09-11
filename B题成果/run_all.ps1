$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Native([string]$Program, [string[]]$Parameters) {
    & $Program @Parameters
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Program (exit $LASTEXITCODE)" }
}
Native 'g++' @('-std=c++17','-O2','tests/test_geometry.cpp','-o','tests/test_geometry.exe')
Native 'g++' @('-std=c++17','-O2','tests/test_physics.cpp','-o','tests/test_physics.exe')
Native './tests/test_geometry.exe' @()
Native './tests/test_physics.exe' @()
Native 'g++' @('-std=c++17','-O2','src/experiment.cpp','-o','experiment.exe')
Native 'g++' @('-std=c++17','-O2','src/robot.cpp','-o','robot.exe')
Native 'g++' @('-std=c++17','-O2','src/q2_design.cpp','-o','q2_design.exe')
Native './q2_design.exe' @('results/q2_candidates.csv')
Native './experiment.exe' @('results/pilot.csv','1','40','950','35','0','0')
Native './experiment.exe' @('results/dev_h900_e35.csv','1','40','900','35','0','0')
Native './experiment.exe' @('results/dev_h990_e35.csv','1','40','990','35','0','0')
Native './experiment.exe' @('results/dev_h950_e20.csv','1','40','950','20','0','0')
Native './experiment.exe' @('results/dev_h950_e50.csv','1','40','950','50','0','0')
Native './experiment.exe' @('results/test_main.csv','10001','200','950','35','0','0')
Native './experiment.exe' @('results/test_square.csv','10001','200','950','35','1','0')
Native './experiment.exe' @('results/test_static.csv','10001','200','950','35','2','0')
Native './experiment.exe' @('results/test_strict.csv','10001','200','950','20','0','0')
Native './experiment.exe' @('results/stress_boundary.csv','40001','100','950','35','0','1','1')
Native './experiment.exe' @('results/stress_collinear.csv','50001','100','950','35','0','2','2')
Native './experiment.exe' @('results/stress_correlated.csv','60001','100','950','35','0','0','3')
Native './experiment.exe' @('results/stress_endpoint.csv','70001','100','950','35','0','0','4')
Native './experiment.exe' @('results/stress_degenerate.csv','80001','100','950','35','0','3','1')
Native './experiment.exe' @('results/representative.csv','10001','1','950','35','0','0','0','results/trace')
Native 'python' @('review/check_geometry.py')
Native 'python' @('review/test_bridge_deadline.py')
Native 'python' @('src/validate_mock.py','--count','30')
Native 'python' @('src/report.py')
Native 'python' @('src/compose_handoff.py')
Write-Output 'All numerical results, figures and manuscript regenerated.'
