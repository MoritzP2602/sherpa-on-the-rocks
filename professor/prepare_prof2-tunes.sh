#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--dry] [--repeat N] [--options \"...\"] -w weightfile (-R | -d refdir) --ipols <ipol.dat> [<ipol2.dat> ...] [label] [--ipols ...]"
    echo "  -w weightfile      : Weight file. Required."
    echo "  -R                 : Take the reference data from Rivet's API."
    echo "  -d refdir          : Take the reference data from this directory."
    echo "                       Exactly one of -R or -d is required."
    echo "  --ipols I [I2 ...] [label]"
    echo "                     : One or more ipol files tuned together in a single fit,"
    echo "                       repeatable. The tune directory is named tune.professor.<label>."
    echo "  --options \"...\"    : (Optional) Extra prof2-tune flags (default: none)."
    echo "  -o outfile         : (Optional) Output filename (default: tunes.txt)."
    echo "  --add              : (Optional) Append to existing outfile instead of overwriting."
    echo "  --dry              : (Optional) Show what would be written without writing it."
    echo "  --repeat N         : (Optional) List every tune N times (default: 1), repeat k"
    echo "                       writing tune.professor.<label>.repeat-k."
    echo "--options may not repeat anything this script already sets: -w, -o, -R or -d."
    exit 1
fi

SETS=()
LABELS=()
WEIGHTS=""
REFDIR=""
USE_RIVET=false
OPTIONS=""
OUTFILE="tunes.txt"
REPEAT=1
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
        --ipols)
            shift
            if [ -z "${1-}" ] || is_option "$1"; then
                echo "--ipols requires at least one ipol file" >&2; exit 1
            fi
            group=""
            label=""
            while [ -n "${1-}" ] && ! is_option "$1"; do
                case "$1" in
                    *.dat)
                        if [ -n "$label" ]; then
                            echo "ERROR: the output label must come last in an --ipols set (got '$1' after '$label')" >&2; exit 1
                        fi
                        group="$group $1" ;;
                    *)
                        if [ -n "$label" ]; then
                            echo "ERROR: --ipols takes at most one output label (got '$label' and '$1')" >&2; exit 1
                        fi
                        label="$1" ;;
                esac
                shift
            done
            if [ -z "$group" ]; then
                echo "ERROR: --ipols requires at least one ipol file (they must end in .dat)" >&2; exit 1
            fi
            SETS+=("${group# }")
            LABELS+=("$label") ;;
        -w|--weights)
            shift
            if [ -z "${1-}" ]; then echo "--weights requires an argument" >&2; exit 1; fi
            WEIGHTS="$1"; shift ;;
        -d|--refdir|--datadir)
            shift
            if [ -z "${1-}" ]; then echo "--refdir requires an argument" >&2; exit 1; fi
            REFDIR="$1"; shift ;;
        -R|--rivet)
            USE_RIVET=true; shift ;;
        --options)
            shift
            if [ -z "${1-}" ]; then echo "--options requires an argument" >&2; exit 1; fi
            OPTIONS="$1"; shift ;;
        -o)
            shift
            if [ -z "${1-}" ]; then echo "-o requires an argument" >&2; exit 1; fi
            OUTFILE="$1"; shift ;;
        --repeat|--repeat=*)
            case "$1" in
                --repeat=*)
                    REPEAT="${1#*=}"; shift ;;
                *)
                    shift
                    if [ -z "${1-}" ]; then echo "--repeat requires an argument" >&2; exit 1; fi
                    REPEAT="$1"; shift ;;
            esac ;;
        --add)
            APPEND=true; shift ;;
        --dry)
            DRY=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if ! [[ "$REPEAT" =~ ^[0-9]+$ ]] || [ "$REPEAT" -lt 1 ]; then
    echo "ERROR: --repeat must be a positive integer (got '$REPEAT')" >&2
    exit 1
fi
if [ "${#SETS[@]}" -eq 0 ]; then
    echo "ERROR: at least one --ipols is required." >&2
    exit 1
fi
if [ $# -gt 0 ]; then
    echo "ERROR: unexpected argument: $1" >&2
    exit 1
fi
if [ -z "$WEIGHTS" ]; then
    echo "ERROR: a weight file is required (-w)." >&2
    exit 1
fi
if [ ! -f "$WEIGHTS" ]; then
    echo "ERROR: Weight file not found: $WEIGHTS" >&2
    exit 1
fi
if [ "$USE_RIVET" = true ] && [ -n "$REFDIR" ]; then
    echo "ERROR: -R and -d cannot be used together." >&2
    exit 1
fi
if [ "$USE_RIVET" = false ] && [ -z "$REFDIR" ]; then
    echo "ERROR: reference data is required: pass either -R or -d refdir." >&2
    exit 1
fi
if [ -n "$REFDIR" ] && [ ! -d "$REFDIR" ]; then
    echo "ERROR: Reference data directory not found: $REFDIR" >&2
    exit 1
fi

check_options() {
    local opt
    for opt in $OPTIONS; do
        case "$opt" in
            -w|--wfile|--wfile=*)
                echo "ERROR: -w is already set by this script. Use -w weightfile instead of passing it in --options." >&2
                exit 1 ;;
            -o|--outdir|--outdir=*)
                echo "ERROR: -o is already set by this script. Give the output label after the --ipols set instead." >&2
                exit 1 ;;
            -R|--rivet)
                echo "ERROR: -R is already set by this script. Pass -R directly instead of in --options." >&2
                exit 1 ;;
            -d|--datadir|--refdir|--datadir=*|--refdir=*)
                echo "ERROR: -d is already set by this script. Pass -d refdir directly instead of in --options." >&2
                exit 1 ;;
        esac
    done
}
check_options

initial_tunes=0
if [ "$APPEND" = true ] && [ -f "$OUTFILE" ]; then
    initial_tunes=$(wc -l < "$OUTFILE")
fi

if [ "$DRY" = false ] && [ "$APPEND" = false ] && [ -f "$OUTFILE" ]; then
    rm "$OUTFILE"
fi

if [ "$DRY" = false ]; then
    mkdir -p condor_output
fi

dry_count=0
emit_tune() {
    if [ "$DRY" = true ]; then
        dry_count=$((dry_count + 1))
        echo "Would list: $1"
    else
        printf '%s\n' "$1" >> "$OUTFILE"
    fi
}

echo "Listing tunes..."
for i in "${!SETS[@]}"; do
    group="${SETS[$i]}"
    label="${LABELS[$i]}"
    for ipol in $group; do
        [ -f "$ipol" ] || echo "Warning: $ipol not found (build it first with prepare_prof2-ipols.sh)"
    done

    base="$group -w $WEIGHTS"
    if [ "$USE_RIVET" = true ]; then
        base="$base -R"
    else
        base="$base -d $REFDIR"
    fi

    for rep in $(seq 1 "$REPEAT"); do
        tag=""
        if [ "$REPEAT" -gt 1 ]; then
            tag=".repeat-$rep"
        fi
        line="$base -o tune.professor${label:+.$label}${tag}"
        if [ -n "$OPTIONS" ]; then
            line="$line $OPTIONS"
        fi
        emit_tune "$line"
    done

    shown=""
    if [ "$REPEAT" -gt 1 ]; then
        shown=".repeat-{1..$REPEAT}"
    fi
    outdir="tune.professor${label:+.$label}${shown}"
    count=$(printf '%s\n' $group | wc -l)
    echo "Listed $REPEAT tune$([ "$REPEAT" -eq 1 ] && echo "" || echo "s") over $count ipol$([ "$count" -eq 1 ] && echo "" || echo "s") ($outdir)"
done

if [ "$DRY" = true ]; then
    echo "Dry run: nothing was written to $OUTFILE."
    echo "Total number of tunes: $dry_count"
    echo ""
    echo "Submit with:"
    echo "  condor_submit ~/sherpa-on-the-rocks/professor/prof2-tune.jdf"
elif [ -f "$OUTFILE" ]; then
    echo "Done! Results written to $OUTFILE."
    total_tunes=$(wc -l < "$OUTFILE")
    if [ "$APPEND" = true ]; then
        added_tunes=$((total_tunes - initial_tunes))
        if [ "$added_tunes" -lt 0 ]; then
            added_tunes=0
        fi
        echo "Added $added_tunes tunes."
    fi
    echo "Total number of tunes: $total_tunes"
    echo ""
    echo "Submit with:"
    echo "  condor_submit ~/sherpa-on-the-rocks/professor/prof2-tune.jdf"
else
    echo "No $OUTFILE found."
fi
