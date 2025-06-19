import Speech
import Foundation
import AVFoundation

class SpeechTranscriber {
    private let speechRecognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechURLRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    
    init(locale: Locale? = nil) {
        // Initialize with specified locale or system default
        if let locale = locale {
            speechRecognizer = SFSpeechRecognizer(locale: locale)
            print("Using language: \(locale.identifier) (\(locale.localizedString(forIdentifier: locale.identifier) ?? "Unknown"))")
        } else {
            speechRecognizer = SFSpeechRecognizer()
            print("Using system default language")
        }
        
        guard speechRecognizer != nil else {
            print("Speech recognizer not available for this locale")
            if locale != nil {
                print("Language '\(locale!.identifier)' may not be supported")
                print("Try running with --list-languages to see available languages")
            }
            exit(1)
        }
        
        guard speechRecognizer!.isAvailable else {
            print("Speech recognizer not available")
            exit(1)
        }
    }
    
    static func listSupportedLanguages() {
        let supportedLocales = SFSpeechRecognizer.supportedLocales()
        print("Supported languages for speech recognition:")
        print("=========================================")
        
        let sortedLocales = supportedLocales.sorted { $0.identifier < $1.identifier }
        
        for locale in sortedLocales {
            let languageName = locale.localizedString(forIdentifier: locale.identifier) ?? "Unknown"
            print("\(locale.identifier.padding(toLength: 12, withPad: " ", startingAt: 0)) - \(languageName)")
        }
        print("\nTotal: \(supportedLocales.count) languages")
    }
    
    func requestPermission() async -> Bool {
        return await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { authStatus in
                switch authStatus {
                case .authorized:
                    continuation.resume(returning: true)
                case .denied, .restricted, .notDetermined:
                    print("Speech recognition permission denied")
                    continuation.resume(returning: false)
                @unknown default:
                    print("Unknown authorization status")
                    continuation.resume(returning: false)
                }
            }
        }
    }
    
    func transcribe(audioFileURL: URL, detailed: Bool = false) async -> (transcript: String, segments: [SFTranscriptionSegment])? {
        return await withCheckedContinuation { continuation in
            recognitionRequest = SFSpeechURLRecognitionRequest(url: audioFileURL)
            
            guard let recognitionRequest = recognitionRequest else {
                print("Unable to create recognition request")
                continuation.resume(returning: nil)
                return
            }
            
            // Configure request for best results
            recognitionRequest.shouldReportPartialResults = false
            recognitionRequest.taskHint = .dictation
            
            recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
                if let error = error {
                    print("Recognition error: \(error.localizedDescription)")
                    continuation.resume(returning: nil)
                    return
                }
                
                if let result = result, result.isFinal {
                    let transcript = result.bestTranscription.formattedString
                    let segments = result.bestTranscription.segments
                    continuation.resume(returning: (transcript: transcript, segments: segments))
                }
            }
        }
    }
    
    func cleanup() {
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
    }
}

// MARK: - Output Formatting

func formatSimpleOutput(_ transcript: String) {
    print("\n=== TRANSCRIPT ===")
    print(transcript)
    print("\n=== END TRANSCRIPT ===")
}

func formatDetailedOutput(_ transcript: String, segments: [SFTranscriptionSegment], options: CLIOptions) {
    print("\n=== DETAILED TRANSCRIPT ===")
    print("Full Text: \(transcript)")
    print("\nWord-Level Breakdown:")
    print(String(repeating: "=", count: 80))
    
    for (index, segment) in segments.enumerated() {
        let timeStart = String(format: "%.2f", segment.timestamp)
        let timeEnd = String(format: "%.2f", segment.timestamp + segment.duration)
        let confidence = String(format: "%.1f%%", Double(segment.confidence) * 100)
        
        print("\n[\(index + 1)] \(timeStart)s - \(timeEnd)s")
        print("Text: \"\(segment.substring)\"")
        
        if options.showConfidence {
            print("Confidence: \(confidence)")
        }
        
        if options.showAlternatives && !segment.alternativeSubstrings.isEmpty {
            print("Alternatives: \(segment.alternativeSubstrings.joined(separator: ", "))")
        }
    }
}

func formatSRTOutput(_ transcript: String, segments: [SFTranscriptionSegment], outputFile: String? = nil) {
    var srtContent = ""
    
    for (index, segment) in segments.enumerated() {
        let startTime = formatSRTTime(segment.timestamp)
        let endTime = formatSRTTime(segment.timestamp + segment.duration)
        
        srtContent += "\(index + 1)\n"
        srtContent += "\(startTime) --> \(endTime)\n"
        srtContent += "\(segment.substring)\n\n"
    }
    
    if let outputFile = outputFile {
        do {
            try srtContent.write(toFile: outputFile, atomically: true, encoding: .utf8)
            print("SRT output saved to: \(outputFile)")
        } catch {
            print("Error writing SRT file: \(error)")
        }
    } else {
        print(srtContent, terminator: "")
    }
}

func formatSRTTime(_ seconds: TimeInterval) -> String {
    let hours = Int(seconds) / 3600
    let minutes = Int(seconds) % 3600 / 60
    let secs = Int(seconds) % 60
    let milliseconds = Int((seconds.truncatingRemainder(dividingBy: 1)) * 1000)
    
    return String(format: "%02d:%02d:%02d,%03d", hours, minutes, secs, milliseconds)
}

func formatJSONOutput(_ transcript: String, segments: [SFTranscriptionSegment], outputFile: String? = nil) {
    struct JSONSegment: Codable {
        let text: String
        let startTime: Double
        let endTime: Double
        let duration: Double
        let confidence: Double
        let alternatives: [String]
    }
    
    struct JSONOutput: Codable {
        let transcript: String
        let segments: [JSONSegment]
        let totalDuration: Double
        let averageConfidence: Double
    }
    
    let jsonSegments = segments.map { segment in
        JSONSegment(
            text: segment.substring,
            startTime: segment.timestamp,
            endTime: segment.timestamp + segment.duration,
            duration: segment.duration,
            confidence: Double(segment.confidence),
            alternatives: segment.alternativeSubstrings
        )
    }
    
    let averageConfidence = segments.isEmpty ? 0.0 : segments.map { Double($0.confidence) }.reduce(0, +) / Double(segments.count)
    let totalDuration = segments.last?.timestamp ?? 0.0 + (segments.last?.duration ?? 0.0)
    
    let output = JSONOutput(
        transcript: transcript,
        segments: jsonSegments,
        totalDuration: totalDuration,
        averageConfidence: averageConfidence
    )
    
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    
    do {
        let jsonData = try encoder.encode(output)
        if let jsonString = String(data: jsonData, encoding: .utf8) {
            if let outputFile = outputFile {
                try jsonString.write(toFile: outputFile, atomically: true, encoding: .utf8)
                print("JSON output saved to: \(outputFile)")
            } else {
                print(jsonString)
            }
        }
    } catch {
        print("Error encoding JSON: \(error)")
    }
}

// MARK: - Command Line Argument Parsing

enum OutputFormat {
    case simple
    case detailed
    case srt
    case json
}

struct CLIOptions {
    var audioFilePath: String?
    var languageCode: String?
    var listLanguages: Bool = false
    var showHelp: Bool = false
    var outputFormat: OutputFormat = .simple
    var showConfidence: Bool = false
    var showAlternatives: Bool = false
    var outputFilePath: String?
}

func parseArguments() -> CLIOptions {
    let arguments = CommandLine.arguments
    var options = CLIOptions()
    var i = 1
    
    while i < arguments.count {
        let arg = arguments[i]
        
        switch arg {
        case "-l", "--language":
            i += 1
            if i < arguments.count {
                options.languageCode = arguments[i]
            } else {
                print("Error: --language requires a language code")
                exit(1)
            }
        case "--list-languages":
            options.listLanguages = true
        case "-h", "--help":
            options.showHelp = true
        case "--detailed":
            options.outputFormat = .detailed
        case "--srt":
            options.outputFormat = .srt
            i += 1
            if i < arguments.count && !arguments[i].hasPrefix("-") {
                options.outputFilePath = arguments[i]
            } else {
                i -= 1 // Back up if next arg is an option or doesn't exist
            }
        case "--json":
            options.outputFormat = .json
            i += 1
            if i < arguments.count && !arguments[i].hasPrefix("-") {
                options.outputFilePath = arguments[i]
            } else {
                i -= 1 // Back up if next arg is an option or doesn't exist
            }
        case "--confidence":
            options.showConfidence = true
        case "--alternatives":
            options.showAlternatives = true
        default:
            if !arg.hasPrefix("-") && options.audioFilePath == nil {
                options.audioFilePath = arg
            } else {
                print("Error: Unknown option '\(arg)'")
                exit(1)
            }
        }
        i += 1
    }
    
    return options
}

func printUsage() {
    let programName = CommandLine.arguments[0]
    print("Speech Transcription CLI")
    print("========================")
    print("")
    print("Usage:")
    print("  \(programName) [options] <audio-file>")
    print("")
    print("Options:")
    print("  -l, --language <code>    Set language (e.g., en-US, es-ES, fr-FR)")
    print("      --list-languages     Show all supported languages")
    print("      --detailed           Show detailed word-level timing and confidence")
    print("      --srt [file]         Output in SRT subtitle format (optional: save to file)")
    print("      --json [file]        Output in JSON format (optional: save to file)")
    print("      --confidence         Show confidence scores")
    print("      --alternatives       Show alternative interpretations")
    print("  -h, --help              Show this help message")
    print("")
    print("Examples:")
    print("  \(programName) recording.wav")
    print("  \(programName) --language es-ES spanish_audio.wav")
    print("  \(programName) --detailed --confidence audio.wav")
    print("  \(programName) --srt subtitles.srt presentation.wav")
    print("  \(programName) --json transcript.json meeting.wav")
}

// MARK: - Main CLI Logic

func runCLI() async {
    let options = parseArguments()
    
    // Handle special options first
    if options.showHelp {
        printUsage()
        return
    }
    
    if options.listLanguages {
        SpeechTranscriber.listSupportedLanguages()
        return
    }
    
    // Check if audio file was provided
    guard let filePath = options.audioFilePath else {
        print("Error: No audio file specified")
        print("")
        printUsage()
        exit(1)
    }
    
    let fileURL = URL(fileURLWithPath: filePath)
    
    // Check if file exists
    guard FileManager.default.fileExists(atPath: filePath) else {
        print("Error: File not found at path: \(filePath)")
        exit(1)
    }
    
    // Validate it's an audio file
    do {
        let audioFile = try AVAudioFile(forReading: fileURL)
        print("Processing audio file: \(filePath)")
        print("Duration: \(audioFile.duration) seconds")
        print("Sample Rate: \(audioFile.fileFormat.sampleRate) Hz")
        print("Channels: \(audioFile.fileFormat.channelCount)")
        
        // Show sampling rate recommendation
        if audioFile.fileFormat.sampleRate != 16000 {
            print("⚠️  Note: For optimal speech recognition, consider using 16kHz sampling rate")
        }
        print("---")
    } catch {
        print("Error: Unable to read audio file. Make sure it's a valid audio file.")
        print("Supported formats: WAV, AIFF, CAF, MP3, M4A, etc.")
        exit(1)
    }
    
    // Create locale if language specified
    var locale: Locale? = nil
    if let languageCode = options.languageCode {
        locale = Locale(identifier: languageCode)
        
        // Validate that the language is supported
        let supportedLocales = SFSpeechRecognizer.supportedLocales()
        if !supportedLocales.contains(locale!) {
            print("Error: Language '\(languageCode)' is not supported")
            print("Run with --list-languages to see available languages")
            exit(1)
        }
    }
    
    // Initialize transcriber with optional locale
    let transcriber = SpeechTranscriber(locale: locale)
    
    // Request permission
    print("Requesting speech recognition permission...")
    let hasPermission = await transcriber.requestPermission()
    guard hasPermission else {
        print("Speech recognition permission is required to use this tool.")
        print("Please enable it in System Preferences > Security & Privacy > Privacy > Speech Recognition")
        exit(1)
    }
    
    print("Permission granted. Starting transcription...")
    
    // Perform transcription
    if let result = await transcriber.transcribe(audioFileURL: fileURL, detailed: true) {
        // Format output based on user preference
        switch options.outputFormat {
        case .simple:
            formatSimpleOutput(result.transcript)
        case .detailed:
            formatDetailedOutput(result.transcript, segments: result.segments, options: options)
        case .srt:
            formatSRTOutput(result.transcript, segments: result.segments, outputFile: options.outputFilePath)
        case .json:
            formatJSONOutput(result.transcript, segments: result.segments, outputFile: options.outputFilePath)
        }
        
        // Show summary stats for non-simple formats
        if options.outputFormat != .simple && options.outputFormat != .srt && options.outputFormat != .json {
            let averageConfidence = result.segments.isEmpty ? 0.0 : result.segments.map { Double($0.confidence) }.reduce(0, +) / Double(result.segments.count)
            print("\n=== SUMMARY ===")
            print("Total segments: \(result.segments.count)")
            print("Average confidence: \(String(format: "%.1f%%", averageConfidence * 100))")
        }
    } else {
        print("Failed to transcribe audio file")
        exit(1)
    }
    
    // Cleanup
    transcriber.cleanup()
    
    if options.outputFormat == .simple {
        print("\nTranscription completed successfully!")
    }
}

// Run the CLI
@main
struct TranscribeApp {
    static func main() async {
        await runCLI()
    }
}

// MARK: - AVAudioFile Extension for Duration

extension AVAudioFile {
    var duration: TimeInterval {
        return Double(length) / fileFormat.sampleRate
    }
}