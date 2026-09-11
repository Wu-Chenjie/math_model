param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputPdf)
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $InputDocx).Path
$destination=[System.IO.Path]::GetFullPath($OutputPdf)
$word=$null;$document=$null;$owned=$false;$saveMode=0
try {
 $word=New-Object -ComObject Word.Application
 if ($word.Visible -or $word.Documents.Count -gt 0) { throw 'Word returned an existing interactive instance; refusing to change it.' }
 $owned=$true;$word.Visible=$false;$word.DisplayAlerts=0
 $document=$word.Documents.Open($source,$false,$true,$false)
 $document.ExportAsFixedFormat($destination,17)
 Write-Output 'Native Word render exported.'
} finally {
 if ($document -ne $null) { $document.Close([ref]$saveMode);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
 if ($word -ne $null) { if($owned){$word.Quit([ref]$saveMode)};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
