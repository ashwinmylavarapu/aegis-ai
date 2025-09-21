import Foundation
import Vision
import ImageIO

func loadCGImage(url: URL) -> CGImage? {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
    return CGImageSourceCreateImageAtIndex(src, 0, nil)
}

@main
struct App {
    static func main() {
        guard CommandLine.arguments.count >= 2 else {
            fputs("usage: mac_ocr <image-path>\n", stderr); exit(2)
        }
        let url = URL(fileURLWithPath: CommandLine.arguments[1])
        guard let cgImage = loadCGImage(url: url) else { fputs("bad image\n", stderr); exit(1) }

        let width = cgImage.width, height = cgImage.height
        var items: [[String: Any]] = []

        let req = VNRecognizeTextRequest { request, error in
            guard let obs = request.results as? [VNRecognizedTextObservation] else { return }
            for o in obs {
                guard let top = o.topCandidates(1).first else { continue }
                let bb = o.boundingBox  // normalized [0,1] in Vision coords (origin bottom-left)
                let x1 = Int((bb.minX * CGFloat(width)).rounded())
                let y1 = Int(((1 - bb.maxY) * CGFloat(height)).rounded())
                let x2 = Int((bb.maxX * CGFloat(width)).rounded())
                let y2 = Int(((1 - bb.minY) * CGFloat(height)).rounded())
                let poly = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                items.append([
                    "poly": poly,
                    "bbox": [x1,y1,x2,y2],
                    "text": top.string,
                    "score": Double(top.confidence)
                ])
            }
        }
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = true

        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do { try handler.perform([req]) } catch {
            fputs("vision error: \(error)\n", stderr); exit(1)
        }

        if let data = try? JSONSerialization.data(withJSONObject: items, options: []),
           let s = String(data: data, encoding: .utf8) {
            print(s)
        }
    }
}
