param (
    [Parameter(Mandatory=$true)]
    [string]$ImagePath
)

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation.UniversalApiContract, ContentType = WindowsRuntime] | Out-Null
    [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] | Out-Null

    $fullPath = [System.IO.Path]::GetFullPath($ImagePath)
    if (-not (Test-Path $fullPath)) {
        Write-Error "File not found: $fullPath"
        exit 1
    }

    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.IsGenericMethodDefinition -and
        $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1

    function Invoke-WinRtAsync($op, [Type]$returnType) {
        $method = $asTaskGeneric.MakeGenericMethod($returnType)
        $task = $method.Invoke($null, @($op))
        $task.Wait()
        return $task.Result
    }

    $fileOp = [Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)
    $storageFile = Invoke-WinRtAsync $fileOp ([Windows.Storage.StorageFile])

    $streamOp = $storageFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    $stream = Invoke-WinRtAsync $streamOp ([Windows.Storage.Streams.IRandomAccessStream])

    $decoderOp = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = Invoke-WinRtAsync $decoderOp ([Windows.Graphics.Imaging.BitmapDecoder])

    $bitmapOp = $decoder.GetSoftwareBitmapAsync()
    $bitmap = Invoke-WinRtAsync $bitmapOp ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        $lang = New-Object Windows.Globalization.Language("en-US")
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    }

    if ($null -eq $engine) {
        Write-Error "No OCR engine available"
        exit 2
    }

    $ocrOp = $engine.RecognizeAsync($bitmap)
    $ocrResult = Invoke-WinRtAsync $ocrOp ([Windows.Media.Ocr.OcrResult])

    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $lines = $ocrResult.Lines | ForEach-Object { $_.Text }; Write-Output ($lines -join [Environment]::NewLine)
} catch {
    Write-Error $_.Exception.ToString()
    exit 3
}

