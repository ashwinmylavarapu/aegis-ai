import Foundation
import Vision
import ImageIO

// --- START: MODIFIED SCRIPT STRUCTURE ---
// The @main attribute and App struct have been removed to make this a valid top-level script.

// Helper function to load a CGImage from a file path
func loadImage(from path: String) -> CGImage? {
    guard let url = URL(string: "file://\(path)"),
          let imageSource = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(imageSource, 0, nil)
    else {
        fputs("Error: Could not load image at path \(path)\n", stderr)
        return nil
    }
    return image
}

// Ensure the correct number of arguments are provided
guard CommandLine.arguments.count == 2 else {
    fputs("Usage: swift mac_ocr.swift <image_path>\n", stderr)
    exit(1)
}

let imagePath = CommandLine.arguments[1]

// Load the image
guard let image = loadImage(from: imagePath) else {
    exit(1)
}

// Create a Vision request for text recognition
let request = VNRecognizeTextRequest { (request, error) in
    if let error = error {
        fputs("Error: Vision request failed: \(error.localizedDescription)\n", stderr)
        return
    }

    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }

    // Concatenate the recognized text
    let recognizedStrings = observations.compactMap { observation in
        observation.topCandidates(1).first?.string
    }
    
    print(recognizedStrings.joined(separator: "\n"))
}

// Set the recognition level to get more accurate results
request.recognitionLevel = .accurate

// Create a request handler and perform the request
let handler = VNImageRequestHandler(cgImage: image, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("Error: Could not perform Vision request: \(error.localizedDescription)\n", stderr)
    exit(1)
}
// --- END: MODIFIED SCRIPT STRUCTURE ---