import os
import sys
import argparse


# Add project root directory to Python path
PROJECT_ROOT = os.path.dirname(
    os.path.abspath(__file__)
)

sys.path.insert(0, PROJECT_ROOT)


def main():

    parser = argparse.ArgumentParser(
        description="GenAI Legacy Code Conversion System"
    )

    # --------------------------------------------------------
    # Source file(s)
    # --------------------------------------------------------

    parser.add_argument(
        "--file",
        "-f",
        nargs="+",
        required=False,
        help=(
            "Path(s) to legacy source file(s). "
            "Supported languages: COBOL, VB and Java."
        )
    )

    # --------------------------------------------------------
    # Output directory
    # --------------------------------------------------------

    parser.add_argument(
        "--output-dir",
        "-o",
        default="output_bundle",
        help="Output directory for generated files."
    )

    # --------------------------------------------------------
    # Target language
    # --------------------------------------------------------

    parser.add_argument(
        "--target-language",
        "-t",
        default="python",
        help="Target language for converted code."
    )

    # --------------------------------------------------------
    # Dashboard
    # --------------------------------------------------------

    parser.add_argument(
        "--dashboard",
        "-d",
        action="store_true",
        help="Launch the Streamlit Human Review Dashboard."
    )

    # --------------------------------------------------------
    # Demo
    # --------------------------------------------------------

    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run the Language Detection and "
            "Chunking demonstration."
        )
    )

    args = parser.parse_args()

    # ========================================================
    # DEMO MODE
    # ========================================================

    if args.demo:

        # If no files are provided, use the default sample.
        file_paths = args.file

        if not file_paths:

            file_paths = [
                "samples/cobol/BILL100.cbl"
            ]

        print()
        print("=" * 70)
        print("LANGUAGE DETECTION AND CHUNKING DEMO")
        print("=" * 70)

        print()
        print("Files supplied:")

        for file_path in file_paths:
            print(f"  - {file_path}")

        try:

            from src.orchestrator.phase1_graph import (
                build_phase1_graph
            )

            graph = build_phase1_graph()

            initial_state = {
                "file_paths": file_paths
            }

            final_state = graph.invoke(
                initial_state
            )

            print()
            print("=" * 70)
            print("DEMO SUMMARY")
            print("=" * 70)

            print(
                f"Files processed : "
                f"{len(file_paths)}"
            )

            print(
                f"Final chunks    : "
                f"{len(final_state.get('chunks', []))}"
            )

            print("=" * 70)

        except Exception as e:

            print(
                f"\nError during demo: {e}",
                file=sys.stderr
            )

            sys.exit(1)

        return

    # ========================================================
    # DASHBOARD MODE
    # ========================================================

    if args.dashboard:

        print(
            "Launching Streamlit Human Review Dashboard..."
        )

        os.system(
            "streamlit run src/dashboard/app.py"
        )

        return

    # ========================================================
    # FULL CONVERSION MODE
    # ========================================================

    # If no file was supplied for normal conversion,
    # use the default sample.
    file_paths = args.file

    if not file_paths:

        file_paths = [
            "samples/cobol/BILL100.cbl"
        ]

    from src.orchestrator.phase2_graph import (
        run_full_conversion
    )

    print(
        f"Starting conversion for files: "
        f"{file_paths}"
    )

    print(
        f"Target language: "
        f"{args.target_language}"
    )

    print(
        f"Output directory: "
        f"{args.output_dir}"
    )

    try:

        final_state = run_full_conversion(
            file_paths=file_paths,
            output_dir=args.output_dir,
            target_language=args.target_language
        )

        print(
            "\nConversion completed successfully!"
        )

        print(
            f"Generated src code: "
            f"{os.path.join(args.output_dir, 'src')}"
        )

        print(
            f"Documentation: "
            f"{os.path.join(args.output_dir, 'docs', 'documentation.md')}"
        )

        print(
            f"Dashboard Report: "
            f"{os.path.join(args.output_dir, 'dashboard_report.json')}"
        )

        print(
            "\nTo view flagged components requiring review, run:"
        )

        print(
            "streamlit run src/dashboard/app.py"
        )

    except Exception as e:

        print(
            f"\nError during conversion: {e}",
            file=sys.stderr
        )

        sys.exit(1)


if __name__ == "__main__":
    main()