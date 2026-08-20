#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--dry] [--only-vals|--only-errs] [--options \"...\"] [-w weightfile] --order M,N [prefix] [--order M,N [prefix] ...] <scan_dir> [<scan_dir2> ...]"
    echo "  <scan_dir>           : Directory containing the grid points (e.g. newscan)."
    echo "  --order M,N [prefix] : Surrogate order, repeatable. The surrogates are named"
    echo "                         <prefix>.app.json and <prefix>.err.json."
    echo "  -w weightfile        : (Optional) Weight file (default: none)."
    echo "  --options \"...\"      : (Optional) Extra app-build flags (default: none)."
    echo "  -o outfile           : (Optional) Output filename (default: builds.txt)."
    echo "  --add                : (Optional) Append to existing outfile instead of overwriting."
    echo "  --dry                : (Optional) Show what would be written without writing it."
    echo "  --only-vals          : (Optional) Only build the value surrogates, not the error ones."
    echo "  --only-errs          : (Optional) Only build the error surrogates, not the value ones."
    echo "--options may not repeat anything this script already sets: --order, -w, -o or --errs."
    exit 1
fi

ORDERS=()
PREFIXES=()
WEIGHTS=""
OPTIONS=""
OUTFILE="builds.txt"
APPEND=false
DRY=false
BUILD_VALUE=true
BUILD_ERRS=true
ONLY_VALS=false
ONLY_ERRS=false
POSITIONAL=()

is_option() {
    case "${1-}" in
        -*) return 0 ;;
        *)  return 1 ;;
    esac
}

while [ $# -gt 0 ]; do
    case "$1" in
        --order|--order=*)
            case "$1" in
                --order=*)
                    order="${1#*=}"; shift ;;
                *)
                    shift
                    if [ -z "${1-}" ]; then echo "--order requires an argument" >&2; exit 1; fi
                    order="$1"; shift ;;
            esac
            # A bare token right after the order is the output prefix; an
            # existing directory is a scan directory instead.
            prefix=""
            if [ -n "${1-}" ] && ! is_option "$1" && [ ! -d "$1" ]; then
                prefix="$1"; shift
            fi
            ORDERS+=("$order"); PREFIXES+=("$prefix") ;;
        -w|--weights)
            shift
            if [ -z "${1-}" ]; then echo "--weights requires an argument" >&2; exit 1; fi
            WEIGHTS="$1"; shift ;;
        --options)
            shift
            if [ -z "${1-}" ]; then echo "--options requires an argument" >&2; exit 1; fi
            OPTIONS="$1"; shift ;;
        -o)
            shift
            if [ -z "${1-}" ]; then echo "-o requires an argument" >&2; exit 1; fi
            OUTFILE="$1"; shift ;;
        --add)
            APPEND=true; shift ;;
        --dry)
            DRY=true; shift ;;
        --only-vals)
            ONLY_VALS=true; shift ;;
        --only-errs)
            ONLY_ERRS=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if [ "$ONLY_VALS" = true ] && [ "$ONLY_ERRS" = true ]; then
    echo "ERROR: --only-vals and --only-errs cannot be used together." >&2
    exit 1
fi
if [ "$ONLY_VALS" = true ]; then
    BUILD_ERRS=false
fi
if [ "$ONLY_ERRS" = true ]; then
    BUILD_VALUE=false
fi
if [ "${#ORDERS[@]}" -eq 0 ]; then
    echo "ERROR: at least one --order is required." >&2
    exit 1
fi
if [ $# -lt 1 ]; then
    echo "ERROR: no scan directory given." >&2
    exit 1
fi
if [ -n "$WEIGHTS" ] && [ ! -f "$WEIGHTS" ]; then
    echo "ERROR: Weight file not found: $WEIGHTS" >&2
    exit 1
fi

SCANS=()
for scan in "$@"; do
    if [ ! -d "$scan" ]; then
        echo "ERROR: Scan directory not found: $scan" >&2
        exit 1
    fi
    SCANS+=("${scan%/}")
done

for order in "${ORDERS[@]}"; do
    if ! [[ "$order" =~ ^[0-9]+,[0-9]+$ ]]; then
        echo "ERROR: --order must look like M,N (got '$order')" >&2
        exit 1
    fi
done

for prefix in "${PREFIXES[@]}"; do
    case "$prefix" in
        *.json)
            echo "ERROR: the output prefix must not end in .json -- .app.json/.err.json is appended by this script (got '$prefix')" >&2
            exit 1 ;;
    esac
done

check_options() {
    local opt
    for opt in $OPTIONS; do
        case "$opt" in
            --order|--order=*)
                echo "ERROR: --order is already set by this script. Use --order M,N instead of passing it in --options." >&2
                exit 1 ;;
            -w|--weights|--weights=*)
                echo "ERROR: -w is already set by this script. Use -w weightfile instead of passing it in --options." >&2
                exit 1 ;;
            -o|--output|--output=*)
                echo "ERROR: -o is already set by this script. Give the output prefix after the --order instead." >&2
                exit 1 ;;
            --errs)
                echo "ERROR: --errs is already set by this script. Use --only-vals or --only-errs to choose which surrogates to build." >&2
                exit 1 ;;
        esac
    done
}
check_options

initial_builds=0
if [ "$APPEND" = true ] && [ -f "$OUTFILE" ]; then
    initial_builds=$(wc -l < "$OUTFILE")
fi

if [ "$DRY" = false ] && [ "$APPEND" = false ] && [ -f "$OUTFILE" ]; then
    rm "$OUTFILE"
fi

if [ "$DRY" = false ]; then
    mkdir -p condor_output
fi

dry_count=0
emit_build() {
    if [ "$DRY" = true ]; then
        dry_count=$((dry_count + 1))
        echo "Would list: $1"
    else
        printf '%s\n' "$1" >> "$OUTFILE"
    fi
}

echo "Listing builds for ${#SCANS[@]} scan director$([ ${#SCANS[@]} -eq 1 ] && echo y || echo ies)..."
for i in "${!ORDERS[@]}"; do
    order="${ORDERS[$i]}"
    prefix="${PREFIXES[$i]}"
    base="${SCANS[*]} --order $order"
    if [ -n "$WEIGHTS" ]; then
        base="$base -w $WEIGHTS"
    fi
    if [ -n "$OPTIONS" ]; then
        base="$base $OPTIONS"
    fi

    names=()
    if [ "$BUILD_VALUE" = true ]; then
        emit_build "$base -o ${prefix:+$prefix.}app.json"
        names+=("${prefix:+$prefix.}app.json")
    fi
    if [ "$BUILD_ERRS" = true ]; then
        emit_build "$base -o ${prefix:+$prefix.}err.json --errs"
        names+=("${prefix:+$prefix.}err.json")
    fi

    listed=${#names[@]}
    joined=$(printf ', %s' "${names[@]}"); joined=${joined:2}
    echo "Listed $listed build$([ "$listed" -eq 1 ] && echo "" || echo "s") for order $order ($joined)"
done

if [ "$DRY" = true ]; then
    echo "Dry run: nothing was written to $OUTFILE."
    echo "Total number of builds: $dry_count"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/apprentice/app-build.jdf"
elif [ -f "$OUTFILE" ]; then
    echo "Done! Results written to $OUTFILE."
    total_builds=$(wc -l < "$OUTFILE")
    if [ "$APPEND" = true ]; then
        added_builds=$((total_builds - initial_builds))
        if [ "$added_builds" -lt 0 ]; then
            added_builds=0
        fi
        echo "Added $added_builds builds."
    fi
    echo "Total number of builds: $total_builds"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/apprentice/app-build.jdf"
else
    echo "No $OUTFILE found."
fi
