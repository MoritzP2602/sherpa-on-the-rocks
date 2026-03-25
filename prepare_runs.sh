#!/bin/bash

OUTFILE="runs.txt"
APPEND=false
EXACT_NAME=false
DEPTH=1
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        -o)
            shift
            if [ -z "${1-}" ]; then echo "-o requires an argument" >&2; exit 1; fi
            OUTFILE="$1"; shift ;;
        --add)
            APPEND=true; shift ;;
        --exact-name)
            EXACT_NAME=true
            shift ;;
        -d|--depth)
            shift
            if [ -z "${1-}" ] || ! [[ "$1" =~ ^[0-9]+$ ]]; then
                echo "--depth requires a non-negative integer argument" >&2
                exit 1
            fi
            DEPTH="$1"
            shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

initial_runs=0
if [ "$APPEND" = true ] && [ -f "$OUTFILE" ]; then
    initial_runs=$(wc -l < "$OUTFILE")
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--exact-name] [--depth N] <folder1> [nsubfolders1] [<folder2> [nsubfolders2] ...]"
    echo "  <folder>      : Directory in which to create or list subfolders"
    echo "  [nsubfolders] : (Optional) Number of subfolders to create in each directory"
    echo "  -o outfile    : (Optional) Output filename (default: runs.txt)"
    echo "  --add         : (Optional) Append to existing outfile instead of overwriting"
    echo "  --exact-name  : Skip only directories with <dirname>.yoda or <dirname>.yoda.gz (default: skip directories with any .yoda/.yoda.gz file)"
    echo "  --depth N     : Creation depth relative to each folder (default: 1)"
    echo "If nsubfolders is given and folder has subdirectories, creates subfolders in each and lists them in $OUTFILE."
    echo "If nsubfolders is given and folder has no subdirectories, creates subfolders directly in folder and lists them in $OUTFILE."
    echo "If nsubfolders is not given, lists all subdirectories of folder in $OUTFILE."
    exit 1
fi

if [ "$APPEND" = false ] && [ -f "$OUTFILE" ]; then
    rm "$OUTFILE"
fi

is_number() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

to_output_path() {
    local abs
    local rel

    abs=$(realpath -m "$1")
    rel=$(realpath --relative-to="$PWD" "$abs" 2>/dev/null)
    if [ -n "$rel" ]; then
        printf '%s\n' "$rel"
        return
    fi

    case "$abs" in
        "$PWD")
            printf '.\n'
            ;;
        "$PWD"/*)
            printf '%s\n' "${abs#"$PWD"/}"
            ;;
        *)
            printf '%s\n' "$abs"
            ;;
    esac
}

has_yaml_file() {
    local dir="$1"
    find "$dir" -maxdepth 1 -type f -name "*.yaml" | grep -q .
}

should_skip_yoda() {
    local dir="$1"
    local dir_name
    dir_name=$(basename "$dir")

    if [ "$EXACT_NAME" = true ]; then
        [ -f "$dir/${dir_name}.yoda" ] || [ -f "$dir/${dir_name}.yoda.gz" ]
    else
        find "$dir" -maxdepth 1 -type f \( -name "*.yoda" -o -name "*.yoda.gz" \) | grep -q .
    fi
}

print_creation_targets() {
    local prefix="$1"
    local depth="$2"

    if [ "$depth" -eq 0 ]; then
        printf '%s\n' "$prefix"
        return
    fi

    find "$prefix" -mindepth "$depth" -maxdepth "$depth" -type d
}

process_folder() {
    local PREFIX="${1%/}"
    local n="$2"
    if [ ! -d "$PREFIX" ]; then
        echo "Warning: No directory named $PREFIX! Skipping..."
        return 1
    fi

    if [ -z "$n" ]; then
        echo "Listing subdirectories in $PREFIX..."
        prefix_has_yaml=false
        listed_total=0
        listed_direct_total=0
        listed_nested_total=0
        if has_yaml_file "$PREFIX"; then
            prefix_has_yaml=true
        fi

        for dir in "$PREFIX"/*; do
            [ -d "$dir" ] || continue

            has_subdirs=false
            for subdir in "$dir"/*; do
                if [ -d "$subdir" ]; then
                    has_subdirs=true
                    break
                fi
            done

            if [ "$has_subdirs" = true ]; then
                if should_skip_yoda "$dir"; then
                    echo "Skipping all subdirectories of $dir (matching YODA already exists in $dir)"
                    continue
                fi

                if ! has_yaml_file "$dir"; then
                    echo "Skipping all subdirectories of $dir (no .yaml file found in $dir)"
                    continue
                fi

                listed_in_dir=0
                for subdir in "$dir"/*; do
                    [ -d "$subdir" ] || continue
                    if should_skip_yoda "$subdir"; then
                        echo "Skipping $subdir (matching YODA found)"
                        continue
                    fi
                    echo "$(to_output_path "$subdir")" >> "$OUTFILE"
                    listed_in_dir=$((listed_in_dir + 1))
                    listed_total=$((listed_total + 1))
                    listed_nested_total=$((listed_nested_total + 1))
                done

                if [ "$listed_in_dir" -gt 0 ]; then
                    echo "Listed $listed_in_dir subdirectories of $dir"
                fi
            else
                if [ "$prefix_has_yaml" = false ]; then
                    echo "Skipping $dir (no .yaml file found in $PREFIX)"
                    continue
                fi

                if should_skip_yoda "$dir"; then
                    echo "Skipping $dir (matching YODA found)"
                    continue
                fi

                echo "$(to_output_path "$dir")" >> "$OUTFILE"
                listed_total=$((listed_total + 1))
                listed_direct_total=$((listed_direct_total + 1))
                echo "Listed $dir"
            fi
        done

        if [ "$listed_total" -gt 0 ]; then
            if [ "$listed_direct_total" -gt 0 ]; then
                echo "Listed $listed_direct_total direct subdirectories of $PREFIX"
                if [ "$listed_nested_total" -gt 0 ]; then
                    echo "Listed $listed_nested_total nested run directories under subdirectories of $PREFIX"
                fi
            fi
        else
            echo "No run directories listed from $PREFIX"
        fi
    else
        width=${#n}
        (( width < 2 )) && width=2

        mapfile -t target_dirs < <(print_creation_targets "$PREFIX" "$DEPTH")
        if [ "$DEPTH" -eq 1 ] && [ ${#target_dirs[@]} -eq 0 ]; then
            target_dirs=("$PREFIX")
        fi

        if [ ${#target_dirs[@]} -eq 0 ]; then
            echo "No target directories found at depth $DEPTH below $PREFIX"
            return 0
        fi

        echo "Creating $n subdirectories for targets at depth $DEPTH in $PREFIX..."
        for dir in "${target_dirs[@]}"; do
            [ -d "$dir" ] || continue

            if ! has_yaml_file "$dir"; then
                echo "Skipping $dir (no .yaml file present)"
                continue
            fi

            if should_skip_yoda "$dir"; then
                echo "Skipping $dir (matching YODA file already exists)"
                continue
            fi

            if [ "$(find "$dir" -mindepth 1 -maxdepth 1 -type d | wc -l)" -gt 0 ]; then
                echo "Skipping $dir (already has subfolders)"
                continue
            fi

            for ((j=0; j<n; j++)); do
                sub_dir=$(printf "$dir/%0${width}d" "$j")
                if [ -d "$sub_dir" ]; then
                    echo "Skipping existing: $sub_dir"
                else
                    mkdir "$sub_dir"
                    echo "Created: $sub_dir"
                fi
                echo "$(to_output_path "$sub_dir")" >> "$OUTFILE"
            done
        done
    fi
}

i=1
while [ $i -le $# ]; do
    folder="${!i}"
    i=$((i + 1))
    
    if [ $i -le $# ]; then
        next_arg="${!i}"
        if is_number "$next_arg"; then
            process_folder "$folder" "$next_arg"
            i=$((i + 1))
        else
            process_folder "$folder" ""
        fi
    else
        process_folder "$folder" ""
    fi
done

if [ -f "$OUTFILE" ]; then
    echo "Done! Results written to $OUTFILE."
    total_runs=$(wc -l < "$OUTFILE")
    if [ "$APPEND" = true ]; then
        added_runs=$((total_runs - initial_runs))
        if [ "$added_runs" -lt 0 ]; then
            added_runs=0
        fi
        echo "Added $added_runs runs."
    fi
    echo "Total number of runs: $total_runs"
else
    echo "No $OUTFILE found, all directories were skipped."
fi
