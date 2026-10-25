using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        bool checkOnly = args.Length == 1 && args[0] == "--check";
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
            string main = Path.Combine(root, "main.py");
            string bootstrap = Path.Combine(root, "bootstrap.py");
            if (!File.Exists(python))
                throw new FileNotFoundException("Не найден Python приложения. Папка .venv должна находиться рядом с GTA 5 RP HELPER.exe.");
            if (!File.Exists(main))
                throw new FileNotFoundException("Не найден main.py. Файлы программы должны находиться рядом с GTA 5 RP HELPER.exe.");
            if (checkOnly)
                return 0;

            ProcessStartInfo start = new ProcessStartInfo
            {
                FileName = python,
                Arguments = "\"" + (File.Exists(bootstrap) ? bootstrap : main) + "\"",
                WorkingDirectory = root,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using (Process process = Process.Start(start))
            {
                if (process == null)
                    throw new InvalidOperationException("Не удалось запустить приложение.");
            }
            return 0;
        }
        catch (Exception error)
        {
            if (!checkOnly)
                MessageBox.Show(error.Message, "GTA 5 RP HELPER", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
