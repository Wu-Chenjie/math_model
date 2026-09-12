param([string]$InputDocx)
$ErrorActionPreference='Stop'
try {
 $w=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
 $path=(Resolve-Path -LiteralPath $InputDocx).Path
 if(-not $w.Visible -and $w.Documents.Count -eq 1){
  $d=$w.Documents.Item(1)
  if($d.ReadOnly -and $d.FullName -eq $path){$mode=0;$d.Close([ref]$mode);$w.Quit([ref]$mode);Write-Output 'Closed leftover hidden read-only render instance.'}
  [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($d)
 }
 [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($w)
} catch {Write-Output 'No matching leftover render instance was changed.'}
