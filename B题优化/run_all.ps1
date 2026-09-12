$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Native([string]$Program, [string[]]$Parameters) {
    & $Program @Parameters
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Program (exit $LASTEXITCODE)" }
}
Native 'g++' @('-std=c++17','-O2','tests/test_route.cpp','-o','tests/test_route.exe')
Native './tests/test_route.exe' @()
Native 'g++' @('-std=c++17','-O2','src/experiment.cpp','-o','experiment.exe')
Native 'g++' @('-std=c++17','-O2','src/robot.cpp','-o','robot.exe')
Native './experiment.exe' @('results/test_baseline.csv','90001','200','950','35','0','0')
Native './experiment.exe' @('results/test_route.csv','90001','200','950','35','3','0')
Native './experiment.exe' @('results/test_joint31.csv','90001','200','950','35','4','0')
Native './experiment.exe' @('results/test_mesh25_nn.csv','90001','200','999','35','5','0','0','-','0','0.16666666666666667','0.91666666666666667','0')
Native './experiment.exe' @('results/test_joint25.csv','90001','200','999','35','5','0','0','-','2','0.16666666666666667','0.91666666666666667','0')
Native './experiment.exe' @('results/test_final.csv','90001','200','999','35','6','0','0','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native './experiment.exe' @('results/stress_boundary.csv','110001','100','999','35','6','1','1','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native './experiment.exe' @('results/stress_collinear.csv','120001','100','999','35','6','2','2','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native './experiment.exe' @('results/stress_correlated.csv','130001','100','999','35','6','0','3','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native './experiment.exe' @('results/stress_endpoint.csv','140001','100','999','35','6','0','4','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native './experiment.exe' @('results/stress_degenerate.csv','150001','100','999','35','6','3','1','-','2','0.16666666666666667','0.91666666666666667','0','1')
Native 'python' @('review/test_bridge_deadline.py')
Native 'python' @('review/src/q2_rational_certificate.py','review/q2_rational_certificate.json')
Native 'python' @('src/validate_mock.py','--count','30')
Native 'python' @('src/analyze.py')
Native 'python' @('src/compose.py')
Write-Output 'Frozen experiments and exact Q2 certificate reproduced.'
