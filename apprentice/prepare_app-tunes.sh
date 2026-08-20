#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--dry] [--repeat N] [--only-errs] [--options \"...\"] -w weightfile -d datafile --surrogates <value.json> [<error.json>] [label] [--surrogates ...]"
    echo "  -w weightfile      : Weight file. Required."
    echo "  -d datafile        : Reference data JSON. Required."
    echo "  --surrogates V [E] [label]"
    echo "                     : Value surrogate V, optionally followed by an error"
    echo "                       surrogate E, repeatable. If E is omitted, no error tune is"
    echo "                       listed for that set. The tune directories are named"
    echo "                       tune.apprentice.<label> and tune.apprentice.err.<label>."
    echo "  --options \"...\"    : (Optional) Extra app-tune2 flags (default: none)."
    echo "  -o outfile         : (Optional) Output filename (default: tunes.txt)."
    echo "  --add              : (Optional) Append to existing outfile instead of overwriting."
    echo "  --dry              : (Optional) Show what would be written without writing it."
    echo "  --repeat N         : (Optional) List every tune N times (default: 1), repeat k"
    echo "                       writing tune.apprentice.<label>.repeat-k."
    echo "  --only-errs        : (Optional) List only the error tunes."
    echo "--options may not repeat anything this script already sets: -o or -e."
    exit 1
fi

VALUES=()
ERRORS=()
LABELS=()
WEIGHTS=""
DATA=""
OPTIONS=""
OUTFILE="tunes.txt"
REPEAT=1
APPEND=false
DRY=false
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
        --surrogates)
            shift
            if [ -z "${1-}" ] || is_option "$1"; then
                echo "--surrogates requires a value surrogate" >&2; exit 1
            fi
            app=""
            err=""
            label=""
            while [ -n "${1-}" ] && ! is_option "$1"; do
                case "$1" in
                    *.json)
                        if [ -n "$label" ]; then
                            echo "ERROR: the output label must come last in a --surrogates set (got '$1' after '$label')" >&2; exit 1
                        fi
                        if [ -z "$app" ]; then
                            app="$1"
                        elif [ -z "$err" ]; then
                            err="$1"
                        else
                            echo "ERROR: --surrogates takes at most two surrogates, a value and an error one (got '$1' as well)" >&2; exit 1
                        fi ;;
                    *)
                        if [ -n "$label" ]; then
                            echo "ERROR: --surrogates takes at most one output label (got '$label' and '$1')" >&2; exit 1
                        fi
                        label="$1" ;;
                esac
                shift
            done
            if [ -z "$app" ]; then
                echo "ERROR: --surrogates requires a value surrogate (it must end in .json)" >&2; exit 1
            fi
            VALUES+=("$app"); ERRORS+=("$err"); LABELS+=("$label") ;;
        -w|--weights)
            shift
            if [ -z "${1-}" ]; then echo "--weights requires an argument" >&2; exit 1; fi
            WEIGHTS="$1"; shift ;;
        -d|--data)
            shift
            if [ -z "${1-}" ]; then echo "--data requires an argument" >&2; exit 1; fi
            DATA="$1"; shift ;;
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
        --only-errs)
            ONLY_ERRS=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if ! [[ "$REPEAT" =~ ^[0-9]+$ ]] || [ "$REPEAT" -lt 1 ]; then
    echo "ERROR: --repeat must be a positive integer (got '$REPEAT')" >&2
    exit 1
fi
if [ "${#VALUES[@]}" -eq 0 ]; then
    echo "ERROR: at least one --surrogates is required." >&2
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
if [ -z "$DATA" ]; then
    echo "ERROR: a reference data file is required (-d)." >&2
    exit 1
fi
if [ ! -f "$WEIGHTS" ]; then
    echo "ERROR: Weight file not found: $WEIGHTS" >&2
    exit 1
fi
if [ ! -f "$DATA" ]; then
    echo "ERROR: Reference data file not found: $DATA" >&2
    exit 1
fi

check_options() {
    local opt
    for opt in $OPTIONS; do
        case "$opt" in
            -o|--outdir|--outdir=*)
                echo "ERROR: -o is already set by this script. Give the output label after the --surrogates set instead." >&2
                exit 1 ;;
            -e|--errorapprox|--errorapprox=*)
                echo "ERROR: -e is already set by this script. Give the error surrogate as the second value of --surrogates." >&2
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
for i in "${!VALUES[@]}"; do
    app="${VALUES[$i]}"
    err="${ERRORS[$i]}"
    label="${LABELS[$i]}"

    [ -f "$app" ] || echo "Warning: $app not found (build it first with prepare_app-builds.sh)"
    if [ -n "$err" ] && [ ! -f "$err" ]; then
        echo "Warning: $err not found (build it first with prepare_app-builds.sh)"
    fi

    listed=0
    for rep in $(seq 1 "$REPEAT"); do
        tag=""
        if [ "$REPEAT" -gt 1 ]; then
            tag=".repeat-$rep"
        fi
        if [ "$ONLY_ERRS" = false ]; then
            emit_tune "$WEIGHTS $DATA $app -o tune.apprentice${label:+.$label}${tag} $OPTIONS"
            listed=$((listed + 1))
        fi
        if [ -n "$err" ]; then
            emit_tune "$WEIGHTS $DATA $app -e $err -o tune.apprentice.err${label:+.$label}${tag} $OPTIONS"
            listed=$((listed + 1))
        fi
    done

    if [ "$listed" -eq 0 ]; then
        echo "Listed 0 tunes for $app (--only-errs, but no error surrogate was given)"
        continue
    fi
    shown=""
    if [ "$REPEAT" -gt 1 ]; then
        shown=".repeat-{1..$REPEAT}"
    fi
    names=()
    if [ "$ONLY_ERRS" = false ]; then names+=("tune.apprentice${label:+.$label}${shown}"); fi
    if [ -n "$err" ];              then names+=("tune.apprentice.err${label:+.$label}${shown}"); fi
    joined=$(printf ', %s' "${names[@]}"); joined=${joined:2}
    echo "Listed $listed tune$([ "$listed" -eq 1 ] && echo "" || echo "s") for $app ($joined)"
done

if [ "$DRY" = true ]; then
    echo "Dry run: nothing was written to $OUTFILE."
    echo "Total number of tunes: $dry_count"
    echo ""
    echo "Submit with:"
    echo "  condor_submit ~/sherpa-on-the-rocks/apprentice/app-tune2.jdf"
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
    echo "  condor_submit ~/sherpa-on-the-rocks/apprentice/app-tune2.jdf"
else
    echo "No $OUTFILE found."
fi
