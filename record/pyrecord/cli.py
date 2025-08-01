import argparse


from .recorder import AudioRecorder


def main():
    """Main function to run when script is executed directly"""
    parser = argparse.ArgumentParser(
        description="Interactive audio recorder and transcriber with Whisper"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Save output files (output.json and output.wav) persistently instead of using temporary files"
    )

    args = parser.parse_args()

    try:
        recorder = AudioRecorder(save_persistent=args.save)
        recorder.run_interactive()

    except KeyboardInterrupt:
        print("\nAu revoir !")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()