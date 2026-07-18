param(
    [ValidateSet('Gui', 'Start', 'Stop')]
    [string]$Action = 'Gui',
    [string]$RootPath
)

$ErrorActionPreference = 'Stop'
$ScriptPath = $MyInvocation.MyCommand.Path
$Root = if ([string]::IsNullOrWhiteSpace($RootPath)) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    [System.IO.Path]::GetFullPath($RootPath)
}
Set-Location -LiteralPath $Root

function Get-ComposeCommand {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker compose version *> $null
        $pluginExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($pluginExitCode -eq 0) { return @('docker', 'compose') }

    $ErrorActionPreference = 'Continue'
    try {
        & docker-compose version *> $null
        $legacyExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($legacyExitCode -eq 0) { return @('docker-compose') }

    throw 'Docker Compose is not installed.'
}

function Invoke-Compose {
    param([string[]]$Compose, [string[]]$Arguments)

    $executable = $Compose[0]
    $allArguments = @($Compose | Select-Object -Skip 1) + $Arguments
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $executable @allArguments 2>&1 | ForEach-Object { Write-Output $_.ToString() }
        $commandExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($commandExitCode -ne 0) {
        throw "Command failed: $($Compose -join ' ') $($Arguments -join ' ')"
    }
}

function Test-Docker {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker info *> $null
        $dockerExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    return $dockerExitCode -eq 0
}

function Start-Crm {
    Write-Output 'Starting Dealership CRM...'
    $compose = Get-ComposeCommand

    if (-not (Test-Docker)) {
        $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $dockerDesktop)) {
            throw 'Docker Desktop is not installed or could not be found.'
        }

        Write-Output 'Docker Desktop is not running. Starting it...'
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
        $ready = $false
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            Start-Sleep -Seconds 2
            if (Test-Docker) { $ready = $true; break }
            if ($attempt % 5 -eq 0) { Write-Output "Waiting for Docker... ($($attempt * 2)s)" }
        }
        if (-not $ready) { throw 'Docker did not become ready within 2 minutes.' }
    }

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker network inspect dealer_crm_net *> $null
        $networkExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($networkExitCode -ne 0) {
        Write-Output 'Creating Docker network dealer_crm_net...'
        $ErrorActionPreference = 'Continue'
        try {
            & docker network create dealer_crm_net 2>&1 | ForEach-Object { Write-Output $_.ToString() }
            $createNetworkExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        if ($createNetworkExitCode -ne 0) { throw 'Could not create Docker network dealer_crm_net.' }
    }

    Write-Output '[1/2] Starting database and CRM application...'
    Invoke-Compose $compose @('up', '-d', '--build')
    Write-Output '[2/2] Running database migrations...'
    Invoke-Compose $compose @('exec', '-T', 'app', 'alembic', 'upgrade', 'head')
    Write-Output 'READY: http://localhost:8756'
}

function Stop-Crm {
    Write-Output 'Stopping Dealership CRM...'
    $compose = Get-ComposeCommand
    if (-not (Test-Docker)) {
        Write-Output 'Docker is not running; there are no reachable containers to stop.'
        return
    }
    Invoke-Compose $compose @('down')
    Write-Output 'STOPPED: All Dealership CRM containers are stopped.'
}

if ($Action -eq 'Start') {
    try { Start-Crm; exit 0 } catch { Write-Output "ERROR: $($_.Exception.Message)"; exit 1 }
}
if ($Action -eq 'Stop') {
    try { Stop-Crm; exit 0 } catch { Write-Output "ERROR: $($_.Exception.Message)"; exit 1 }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Dealership CRM Launcher'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(900, 600)
$form.MinimumSize = New-Object System.Drawing.Size(720, 480)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$toolbar = New-Object System.Windows.Forms.FlowLayoutPanel
$toolbar.Dock = 'Top'
$toolbar.Height = 58
$toolbar.Padding = New-Object System.Windows.Forms.Padding(10)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'Start CRM'
$startButton.Size = New-Object System.Drawing.Size(125, 34)
$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'Stop CRM'
$stopButton.Size = New-Object System.Drawing.Size(125, 34)
$openButton = New-Object System.Windows.Forms.Button
$openButton.Text = 'Open CRM'
$openButton.Size = New-Object System.Drawing.Size(125, 34)
$clearButton = New-Object System.Windows.Forms.Button
$clearButton.Text = 'Clear Log'
$clearButton.Size = New-Object System.Drawing.Size(125, 34)
$toolbar.Controls.AddRange(@($startButton, $stopButton, $openButton, $clearButton))

$logBox = New-Object System.Windows.Forms.RichTextBox
$logBox.Dock = 'Fill'
$logBox.ReadOnly = $true
$logBox.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 24)
$logBox.ForeColor = [System.Drawing.Color]::Gainsboro
$logBox.Font = New-Object System.Drawing.Font('Consolas', 10)
$logBox.WordWrap = $false

$status = New-Object System.Windows.Forms.StatusStrip
$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = 'Ready'
$status.Items.Add($statusLabel) | Out-Null

$form.Controls.Add($logBox)
$form.Controls.Add($toolbar)
$form.Controls.Add($status)

$script:activeProcess = $null
function Add-Log([string]$line) {
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    $form.BeginInvoke([Action]{
        $logBox.AppendText("[$(Get-Date -Format 'HH:mm:ss')] $line`r`n")
        $logBox.SelectionStart = $logBox.TextLength
        $logBox.ScrollToCaret()
    }) | Out-Null
}

function Set-Busy([bool]$busy, [string]$message) {
    $form.BeginInvoke([Action]{
        $startButton.Enabled = -not $busy
        $stopButton.Enabled = -not $busy
        $statusLabel.Text = $message
    }) | Out-Null
}

function Invoke-LauncherAction([string]$requestedAction) {
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) { return }
    Set-Busy $true "$requestedAction in progress..."
    Add-Log "===== $requestedAction ====="

    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = 'powershell.exe'
    $info.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -Action $requestedAction"
    $info.WorkingDirectory = $Root
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    $process.EnableRaisingEvents = $true
    $process.add_OutputDataReceived({ param($sender, $event) if ($null -ne $event.Data) { Add-Log $event.Data } })
    $process.add_ErrorDataReceived({ param($sender, $event) if ($null -ne $event.Data) { Add-Log "ERROR: $($event.Data)" } })
    $process.add_Exited({
        $exitCode = $process.ExitCode
        Add-Log $(if ($exitCode -eq 0) { 'Operation completed successfully.' } else { "Operation failed (exit code $exitCode)." })
        Set-Busy $false $(if ($exitCode -eq 0) { 'Ready' } else { 'Failed - review the log' })
    })
    $script:activeProcess = $process
    $process.Start() | Out-Null
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
}

$startButton.Add_Click({ Invoke-LauncherAction 'Start' })
$stopButton.Add_Click({ Invoke-LauncherAction 'Stop' })
$openButton.Add_Click({ Start-Process 'http://localhost:8756' })
$clearButton.Add_Click({ $logBox.Clear() })
$form.Add_FormClosing({
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) {
        $_.Cancel = $true
        [System.Windows.Forms.MessageBox]::Show('Please wait for the current operation to finish.', 'Dealership CRM') | Out-Null
    }
})

$logBox.AppendText("[$(Get-Date -Format 'HH:mm:ss')] Launcher ready. Choose Start CRM or Stop CRM.`r`n")
[System.Windows.Forms.Application]::Run($form)
