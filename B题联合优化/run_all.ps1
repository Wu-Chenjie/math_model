param([switch]$AllStages)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
function Native([string]$Program,[string[]]$Parameters){& $Program @Parameters;if($LASTEXITCODE -ne 0){throw "Failed $Program ($LASTEXITCODE)"}}
$tests='test_belief_dp','test_selection','test_controller','test_joint','test_retreat','test_clear_neighborhood','test_optical_order','test_q3_radius','test_scan_fee','test_action_budget','test_discovery','test_adaptive_optical'
foreach($test in $tests){Native 'g++' @('-std=c++17','-O3',('tests/'+$test+'.cpp'),'-o',('tests/'+$test+'.exe'));Native ('./tests/'+$test+'.exe') @()}
Native 'python' @('tests/q3_coverage_bound.py')
Native 'g++' @('-std=c++17','-O3','src/benchmark.cpp','-o','benchmark.exe')
Native 'g++' @('-std=c++17','-O3','src/robot.cpp','-o','robot.exe')
Native 'python' @('tests/test_cli.py')
Native 'python' @('tests/test_bridge_deadline.py')
$stages=if($AllStages){1,2,3}else{3}
foreach($stage in $stages){
    $method=if($stage -eq 1){38}elseif($stage -eq 2){39}else{56}
    $start=if($stage -eq 1){1510001}elseif($stage -eq 2){1710001}else{1910001}
    $suffix=if($stage -eq 1){''}else{[string]$stage}
    Native './benchmark.exe' @(('results/iid'+$suffix+'_baseline.csv'),[string]$start,'200','0','0','0')
    Native './benchmark.exe' @(('results/iid'+$suffix+'_final.csv'),[string]$start,'200','0',[string]$method,[string]$method)
    for($k=1;$k -le 5;++$k){foreach($m in 0,$method){$name=if($stage -eq 1){'results/stress'+$k+'_'+$m+'.csv'}else{'results/stress'+$stage+'_'+$k+'_'+$m+'.csv'};Native './benchmark.exe' @($name,[string]($start+10000*$k),'40',[string]$k,[string]$m,[string]$m)}}
    $script=if($stage -eq 1){'src/analyze_joint.py'}else{'src/analyze_stage'+$stage+'.py'};Native 'python' @($script)
}
Native 'python' @('src/validate_mock.py','--strategy','joint','--count','10')
Native 'python' @('src/validate_mock.py','--strategy','baseline','--count','2')
Native 'python' @('src/write_report_stage3.py')
Native 'python' @('src/final_check_joint.py')
