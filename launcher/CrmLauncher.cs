using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed class CrmLauncher : Form
{
    private readonly string root;
    private readonly Button actionButton = new Button();
    private readonly Button openButton = new Button();
    private readonly Button updateButton = new Button();
    private readonly Label runStatus = new Label();
    private readonly ComboBox branchCombo = new ComboBox();
    private readonly RichTextBox log = new RichTextBox();
    private readonly Timer statusTimer = new Timer();
    private Process activeProcess;
    private bool isRunning;
    private bool checkingStatus;

    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try { Application.Run(new CrmLauncher()); }
        catch (Exception ex)
        {
            File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher_crash.log"), ex.ToString());
            MessageBox.Show(ex.ToString(), "CRM Launcher crashed", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private CrmLauncher()
    {
        root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        Text = "Dealership CRM Launcher";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(940, 620);
        MinimumSize = new Size(900, 480);
        Font = new Font("Segoe UI", 10F);

        var header = new Panel { Dock = DockStyle.Top, Height = 82, Padding = new Padding(12) };
        actionButton.Size = new Size(130, 42);
        actionButton.Location = new Point(12, 20);
        actionButton.Click += async delegate { await RunActionAsync(isRunning ? "Stop" : "Start"); };

        openButton.Text = "Open CRM";
        openButton.Size = new Size(120, 42);
        openButton.Location = new Point(152, 20);
        openButton.Click += delegate { Process.Start("http://localhost:8756"); };

        runStatus.AutoSize = false;
        runStatus.TextAlign = ContentAlignment.MiddleCenter;
        runStatus.Font = new Font("Segoe UI Semibold", 10F, FontStyle.Bold);
        runStatus.Size = new Size(150, 32);
        runStatus.Location = new Point(290, 25);

        var rightPanel = new Panel { Dock = DockStyle.Right, Width = 390 };
        var branchTitle = new Label
        {
            Text = "Branch:",
            AutoSize = false,
            TextAlign = ContentAlignment.MiddleRight,
            Location = new Point(0, 26),
            Size = new Size(62, 30)
        };
        branchCombo.DropDownStyle = ComboBoxStyle.DropDownList;
        branchCombo.Size = new Size(190, 30);
        branchCombo.Location = new Point(67, 26);

        updateButton.Text = "Update";
        updateButton.Size = new Size(110, 42);
        updateButton.Location = new Point(267, 20);
        updateButton.Click += async delegate { await UpdateAsync(); };
        rightPanel.Controls.AddRange(new Control[] { branchTitle, branchCombo, updateButton });
        header.Controls.AddRange(new Control[] { actionButton, openButton, runStatus, rightPanel });

        log.Dock = DockStyle.Fill;
        log.ReadOnly = true;
        log.BackColor = Color.FromArgb(24, 24, 24);
        log.ForeColor = Color.Gainsboro;
        log.Font = new Font("Consolas", 10F);
        log.WordWrap = false;
        log.DetectUrls = false;

        Controls.Add(log);
        Controls.Add(header);
        FormClosing += OnClosing;
        Shown += async delegate
        {
            AppendLog("Launcher ready.");
            RefreshBranches();
            await RefreshStatusAsync();
            statusTimer.Start();
        };

        statusTimer.Interval = 3000;
        statusTimer.Tick += async delegate { await RefreshStatusAsync(); };
        SetRunningUi(false);
    }

    private void AppendLog(string line)
    {
        if (string.IsNullOrWhiteSpace(line)) return;
        if (InvokeRequired) { BeginInvoke(new Action<string>(AppendLog), line); return; }
        log.AppendText("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + line + Environment.NewLine);
        log.SelectionStart = log.TextLength;
        log.ScrollToCaret();
    }

    private void SetRunningUi(bool running)
    {
        isRunning = running;
        actionButton.Text = running ? "Stop CRM" : "Start CRM";
        actionButton.BackColor = running ? Color.FromArgb(205, 70, 70) : Color.FromArgb(55, 160, 90);
        actionButton.ForeColor = Color.White;
        runStatus.Text = running ? "● RUNNING" : "● STOPPED";
        runStatus.ForeColor = running ? Color.FromArgb(25, 145, 65) : Color.FromArgb(190, 55, 55);
    }

    private async Task RefreshStatusAsync()
    {
        if (checkingStatus || activeProcess != null) return;
        checkingStatus = true;
        try
        {
            int code = await RunQuietAsync("docker.exe", "inspect -f {{.State.Running}} dealer_crm_app");
            SetRunningUi(code == 0);
        }
        catch (Exception ex)
        {
            SetRunningUi(false);
            AppendLog("Status check failed: " + ex.Message);
        }
        finally { checkingStatus = false; }
    }

    private void RefreshBranches()
    {
        try
        {
            string safeRoot = Quote(root.Replace('\\', '/'));
            string current = RunCapture("git.exe", "-c safe.directory=" + safeRoot + " branch --show-current").Trim();
            string refs = RunCapture("git.exe", "-c safe.directory=" + safeRoot + " for-each-ref --format=%(refname:short) refs/heads refs/remotes/origin");
            var branches = new List<string>();
            foreach (string rawLine in refs.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string branch = rawLine.Trim();
                if (branch == "origin" || branch == "origin/HEAD") continue;
                if (branch.StartsWith("origin/")) branch = branch.Substring(7);
                if (!branches.Contains(branch)) branches.Add(branch);
            }
            branches.Sort(StringComparer.OrdinalIgnoreCase);
            branchCombo.BeginUpdate();
            branchCombo.Items.Clear();
            foreach (string branch in branches) branchCombo.Items.Add(branch);
            branchCombo.EndUpdate();
            if (!string.IsNullOrWhiteSpace(current) && branchCombo.Items.Contains(current)) branchCombo.SelectedItem = current;
            else if (branchCombo.Items.Count > 0) branchCombo.SelectedIndex = 0;
        }
        catch (Exception ex)
        {
            branchCombo.Items.Clear();
            branchCombo.Items.Add("unavailable");
            branchCombo.SelectedIndex = 0;
            AppendLog("Git: " + ex.Message);
        }
    }

    private async Task RunActionAsync(string action)
    {
        string tempDirectory = Path.Combine(Path.GetTempPath(), "DealershipCRMLauncher");
        string script = Path.Combine(tempDirectory, "crm_launcher.ps1");
        Directory.CreateDirectory(tempDirectory);
        using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("CrmLauncher.Script"))
        {
            if (resource == null) throw new InvalidOperationException("Embedded launcher script is missing.");
            using (var output = File.Create(script)) resource.CopyTo(output);
        }
        await RunLoggedAsync("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File " + Quote(script) + " -Action " + action + " -RootPath " + Quote(root), action);
        try { File.Delete(script); } catch { }
        await RefreshStatusAsync();
    }

    private async Task UpdateAsync()
    {
        string branch = branchCombo.SelectedItem == null ? "" : branchCombo.SelectedItem.ToString();
        if (string.IsNullOrWhiteSpace(branch) || branch == "unavailable")
        {
            AppendLog("Update cancelled: current branch could not be determined.");
            return;
        }
        await RunLoggedAsync("git.exe", "-c safe.directory=" + Quote(root.Replace('\\', '/')) + " pull origin " + Quote(branch), "Update");
        RefreshBranches();
    }

    private async Task RunLoggedAsync(string file, string arguments, string label)
    {
        if (activeProcess != null) return;
        actionButton.Enabled = false;
        updateButton.Enabled = false;
        AppendLog("===== " + label + " =====");
        var process = CreateProcess(file, arguments, true);
        activeProcess = process;
        process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) AppendLog(e.Data); };
        process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) AppendLog("ERROR: " + e.Data); };
        try
        {
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            await Task.Run(delegate { process.WaitForExit(); });
            AppendLog(process.ExitCode == 0 ? "Operation completed successfully." : "Operation failed (exit code " + process.ExitCode + ").");
        }
        catch (Exception ex) { AppendLog("ERROR: " + ex.Message); }
        finally
        {
            process.Dispose();
            activeProcess = null;
            actionButton.Enabled = true;
            updateButton.Enabled = true;
        }
    }

    private static Process CreateProcess(string file, string arguments, bool redirect)
    {
        return new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = file,
                Arguments = arguments,
                WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = redirect,
                RedirectStandardError = redirect,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            }
        };
    }

    private static Task<int> RunQuietAsync(string file, string arguments)
    {
        return Task.Run(delegate
        {
            using (var process = CreateProcess(file, arguments, true))
            {
                process.Start();
                process.WaitForExit();
                return process.ExitCode;
            }
        });
    }

    private static string RunCapture(string file, string arguments)
    {
        using (var process = CreateProcess(file, arguments, true))
        {
            process.Start();
            string output = process.StandardOutput.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode != 0) throw new InvalidOperationException(process.StandardError.ReadToEnd().Trim());
            return output;
        }
    }

    private static string Quote(string value) { return "\"" + value.Replace("\"", "\\\"") + "\""; }

    private void OnClosing(object sender, FormClosingEventArgs e)
    {
        if (activeProcess == null) return;
        e.Cancel = true;
        MessageBox.Show("Please wait for the current operation to finish.", "Dealership CRM");
    }
}
