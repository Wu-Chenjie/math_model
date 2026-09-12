param([switch]$Full)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
function Native([string]$Program,[string[]]$Parameters){& $Program @Parameters;if($LASTEXITCODE -ne 0){throw "Failed $Program ($LASTEXITCODE)"}}
foreach($test in Get-ChildItem -LiteralPath tests -Filter '*.cpp'){
    Native 'g++' @('-std=c++17','-O3',$test.FullName,'-o',('tests/'+$test.BaseName+'.exe'))
    Native ('./tests/'+$test.BaseName+'.exe') @()
}
Native 'python' @('tests/test_pair_analysis.py')
Native 'python' @('tests/q3_coverage_bound.py')
Native 'g++' @('-std=c++17','-O3','src/benchmark.cpp','-o','benchmark.exe')
Native 'g++' @('-std=c++17','-O3','src/robot.cpp','-o','robot.exe')
Native 'python' @('tests/test_cli.py')
# Run deadline tests before CPU-heavy benchmarks to reduce timing noise.
Native 'python' @('tests/test_bridge_deadline.py')
if($Full){
    foreach($part in 'a','b'){
        $start=if($part -eq 'a'){2310001}else{2310101}
        foreach($method in 56,78){Native './benchmark.exe' @(('results/iid'+$method+'_'+$part+'.csv'),[string]$start,'100','0',[string]$method,[string]$method)}
    }
    foreach($group in 1..5){foreach($method in 56,78){Native './benchmark.exe' @(('results/stress'+$group+'_'+$method+'.csv'),[string](2310001+10000*$group),'40',[string]$group,[string]$method,[string]$method)}}
}
Native 'python' @('src/pair_analysis.py','--baseline','results/iid56_a.csv','results/iid56_b.csv','--candidate','results/iid78_a.csv','results/iid78_b.csv','--expected-per-problem','200','--shortcut-check','--output','results/independent_summary.json')
$base=@(Get-ChildItem -LiteralPath results -Filter 'stress*_56.csv' | ForEach-Object {$_.FullName})
$candidate=@(Get-ChildItem -LiteralPath results -Filter 'stress*_78.csv' | ForEach-Object {$_.FullName})
Native 'python' (@('src/pair_analysis.py','--baseline')+$base+@('--candidate')+$candidate+@('--expected-per-problem','40','--shortcut-check','--output','results/stress_summary.json'))
Native 'python' @('src/validate_mock.py','--strategy','joint','--count','10')
Native 'python' @('src/validate_mock.py','--strategy','previous','--count','10')
Native 'python' @('src/write_current_report.py')
