using System;
using System.IO;
using System.Threading.Tasks;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage;
using Windows.Storage.Streams;

class Program {
    static int Main(string[] args) {
        if (args.Length == 0) {
            Console.WriteLine("Usage: winocr_cli <image_path>");
            return 1;
        }
        try {
            string text = RunOcrAsync(args[0]).GetAwaiter().GetResult();
            Console.WriteLine(text);
            return 0;
        } catch (Exception ex) {
            Console.Error.WriteLine("OCR Error: " + ex.ToString());
            return 2;
        }
    }

    static async Task<string> RunOcrAsync(string imagePath) {
        string fullPath = Path.GetFullPath(imagePath);
        StorageFile file = await WindowsRuntimeSystemExtensions.AsTask(StorageFile.GetFileFromPathAsync(fullPath));
        using (IRandomAccessStream stream = await WindowsRuntimeSystemExtensions.AsTask(file.OpenAsync(FileAccessMode.Read))) {
            BitmapDecoder decoder = await WindowsRuntimeSystemExtensions.AsTask(BitmapDecoder.CreateAsync(stream));
            SoftwareBitmap bitmap = await WindowsRuntimeSystemExtensions.AsTask(decoder.GetSoftwareBitmapAsync());
            OcrEngine engine = OcrEngine.TryCreateFromUserProfileLanguages();
            if (engine == null) {
                throw new Exception("Unable to create OCR engine from user languages.");
            }
            OcrResult result = await WindowsRuntimeSystemExtensions.AsTask(engine.RecognizeAsync(bitmap));
            return result.Text;
        }
    }
}
