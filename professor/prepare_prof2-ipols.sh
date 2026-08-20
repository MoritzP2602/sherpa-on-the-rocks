#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--dry] [--options \"...\"] [-w weightfile] --order N [prefix] [--order N [prefix] ...] <scan_dir>"
    echo "  <scan_dir>         : Directory containing the grid points (e.g. newscan)."
    echo "  --order N [prefix] : Interpolation order, repeatable. The ipol is named"
    echo "                       <prefix>.ipol.dat."
    echo "  -w weightfile      : (Optional) Weight file (default: none)."
    echo "  --options \"...\"    : (Optional) Extra prof2-ipol flags (default: none)."
    echo "  -o outfile         : (Optional) Output filename (default: ipols.txt)."
    echo "  --add              : (Optional) Append to existing outfile instead of overwriting."
    echo "  --dry              : (Optional) Show what would be written without writing it."
    echo "--options may not repeat anything this script already sets: --order, -w, or -j"
    exit 1
fi

ORDERS=()
PREFIXES=()
WEIGHTS=""
OPTIONS=""
OUTFILE="ipols.txt"
APPEND=false
DRY=false
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
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if [ "${#ORDERS[@]}" -eq 0 ]; then
    echo "ERROR: at least one --order is required." >&2
    exit 1
fi
if [ $# -lt 1 ]; then
    echo "ERROR: no scan directory given." >&2
    exit 1
fi
if [ $# -gt 1 ]; then
    echo "ERROR: prof2-ipol takes exactly one runs directory (got $#)." >&2
    exit 1
fi
if [ -n "$WEIGHTS" ] && [ ! -f "$WEIGHTS" ]; then
    echo "ERROR: Weight file not found: $WEIGHTS" >&2
    exit 1
fi

SCAN="${1%/}"
if [ ! -d "$SCAN" ]; then
    echo "ERROR: Scan directory not found: $SCAN" >&2
    exit 1
fi

for order in "${ORDERS[@]}"; do
    if ! [[ "$order" =~ ^[0-9]+$ ]]; then
        echo "ERROR: --order must be an integer (got '$order')" >&2
        exit 1
    fi
done

for prefix in "${PREFIXES[@]}"; do
    case "$prefix" in
        *.dat)
            echo "ERROR: the output prefix must not end in .dat -- .ipol.dat is appended by this script (got '$prefix')" >&2
            exit 1 ;;
    esac
done

check_options() {
    local opt
    for opt in $OPTIONS; do
        case "$opt" in
            -j|-j=*|--multi|--multi=*)
                echo "ERROR: -j is set from NPROC. Use 'NPROC=N condor_submit ...' instead of passing -j in --options." >&2
                exit 1 ;;
            --order|--order=*)
                echo "ERROR: --order is already set by this script. Use --order N instead of passing it in --options." >&2
                exit 1 ;;
            -w|--wfile|--wfile=*)
                echo "ERROR: -w is already set by this script. Use -w weightfile instead of passing it in --options." >&2
                exit 1 ;;
        esac
    done
}
check_options

initial_ipols=0
if [ "$APPEND" = true ] && [ -f "$OUTFILE" ]; then
    initial_ipols=$(wc -l < "$OUTFILE")
fi

if [ "$DRY" = false ] && [ "$APPEND" = false ] && [ -f "$OUTFILE" ]; then
    rm "$OUTFILE"
fi

if [ "$DRY" = false ]; then
    mkdir -p condor_output
fi

dry_count=0
emit_ipol() {
    if [ "$DRY" = true ]; then
        dry_count=$((dry_count + 1))
        echo "Would list: $1"
    else
        printf '%s\n' "$1" >> "$OUTFILE"
    fi
}

echo "Listing ipols for $SCAN..."
for i in "${!ORDERS[@]}"; do
    order="${ORDERS[$i]}"
    prefix="${PREFIXES[$i]}"
    ipol="${prefix:+$prefix.}ipol.dat"
    line="$SCAN $ipol --order $order"
    if [ -n "$WEIGHTS" ]; then
        line="$line -w $WEIGHTS"
    fi
    if [ -n "$OPTIONS" ]; then
        line="$line $OPTIONS"
    fi
    emit_ipol "$line"
    echo "Listed 1 ipol for order $order ($ipol)"
done

if [ "$DRY" = true ]; then
    echo "Dry run: nothing was written to $OUTFILE."
    echo "Total number of ipols: $dry_count"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/professor/prof2-ipol.jdf"
elif [ -f "$OUTFILE" ]; then
    echo "Done! Results written to $OUTFILE."
    total_ipols=$(wc -l < "$OUTFILE")
    if [ "$APPEND" = true ]; then
        added_ipols=$((total_ipols - initial_ipols))
        if [ "$added_ipols" -lt 0 ]; then
            added_ipols=0
        fi
        echo "Added $added_ipols ipols."
    fi
    echo "Total number of ipols: $total_ipols"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/professor/prof2-ipol.jdf"
else
    echo "No $OUTFILE found."
fi
