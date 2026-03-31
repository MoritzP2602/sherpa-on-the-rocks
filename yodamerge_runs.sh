#!/bin/bash

REMOVE_SUBDIRS=false
CHUNK_SIZE=0
NMAX=-1
OUTPUT_DIR=""
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        --rm)
            REMOVE_SUBDIRS=true; shift ;;
        --chunked)
            CHUNK_SIZE="$2"; shift 2 ;;
        --nmax)
            NMAX="$2"; shift 2 ;;
        --output|-o)
            OUTPUT_DIR="${2%/}"; shift 2 ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--rm] [--chunked N] [--nmax N] [--output|-o DIR] <folder1> [<folder2> ...] [nproc]"
    echo "  <folder>        : Directory containing subfolders with YODA files"
    echo "  [nproc]         : Number of parallel jobs (default: 4). Use 1 for sequential processing."
    echo "  --rm            : (Optional) Remove merged subdirectories after successful merge to free space"
    echo "  --chunked N     : (Optional) Merge in chunks of N files (reduces memory usage). Processes nproc chunks in parallel."
    echo "  --nmax N        : (Optional) Maximum number of yoda files to merge per directory (default: all)"
    echo "  --output|-o DIR : (Optional) Output directory for merged files (preserves input structure)"
    echo "If subdirectories have their own subfolders, merges all .yoda/.yoda.gz files from nested subdirectories into a single .yoda file in each subdirectory."
    echo "If subdirectories do not have subfolders, merges all .yoda/.yoda.gz files from all subdirectories into a single .yoda file in the parent folder."
    echo "With --chunked mode: splits files into chunks of N files, processes nproc chunks in parallel, then merges results."
    exit 1
fi

is_number() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

FOLDERS=()
NPROC=4
NPROC_USER_SET=false

for arg in "$@"; do
    if is_number "$arg" && [ "$arg" = "${@: -1}" ]; then
        NPROC="$arg"
        NPROC_USER_SET=true
    else
        FOLDERS+=("$arg")
    fi
done

if ! is_number "$NPROC" || [ "$NPROC" -lt 1 ]; then
    echo "Error: nproc must be a positive integer (>= 1)."
    exit 1
fi

if [ ${#FOLDERS[@]} -eq 0 ]; then
    echo "Error: No folders provided!"
    exit 1
fi

if [ -n "$OUTPUT_DIR" ] && [ ${#FOLDERS[@]} -ne 1 ]; then
    echo "Error: --output|-o can only be used with exactly one input folder."
    exit 1
fi

merge_dir() {
    dir="$1"
    YODA=$(basename "$dir")
    
    if [ -n "$OUTPUT_DIR" ]; then
        rel_path="${dir#$BASE_INPUT_DIR/}"
        out_dir="$OUTPUT_DIR/$rel_path"
        OUTFILE="$out_dir/${YODA}.yoda"
    else
        out_dir="$dir"
        OUTFILE="$dir/${YODA}.yoda"
    fi
    
    if [ -f "$OUTFILE" ]; then
        echo "Skipping $dir: $OUTFILE already exists"
        return
    fi

    mapfile -t FILES < <(find "$dir" -mindepth 2 -maxdepth 2 -type f \( -name '*.yoda' -o -name '*.yoda.gz' \))

    if [ "$NMAX" -gt 0 ] && [ "${#FILES[@]}" -gt "$NMAX" ]; then
        echo "Limiting to first $NMAX files (out of ${#FILES[@]} found)..."
        FILES=("${FILES[@]:0:$NMAX}")
    fi

    if [ "${#FILES[@]}" -eq 0 ]; then
        echo "Skipping $dir: No .yoda.gz/.yoda files found in subdirectories."
    else
        if [ -n "$OUTPUT_DIR" ]; then
            mkdir -p "$out_dir"
        fi
        if [ "$CHUNK_SIZE" -gt 0 ]; then
            echo "Merging YODA files into $OUTFILE using chunked mode..."
            merge_chunked "$out_dir" "$OUTFILE" "${FILES[@]}"
        else
            echo "Merging YODA files into $OUTFILE..."
            if command -v yodamerge >/dev/null 2>&1; then
                yodamerge "${FILES[@]}" -o "$OUTFILE"
                if [ "$REMOVE_SUBDIRS" = true ] && [ -f "$OUTFILE" ] && [ -z "$OUTPUT_DIR" ]; then
                    for subdir in "$dir"/*; do
                        if [ -d "$subdir" ]; then
                            echo "Removing $subdir..."
                            rm -rf "$subdir"
                        fi
                    done
                fi
            else
                echo "Error: yodamerge command not found. Please install YODA or adjust the script to point to the correct path!"
                exit 1
            fi
        fi
    fi
}

merge_flat() {
    PREFIX="${1%/}"
    
    if [ -n "$OUTPUT_DIR" ]; then
        out_dir="$OUTPUT_DIR"
        YODA=$(basename "$OUTPUT_DIR")
        OUTFILE="$out_dir/${YODA}.yoda"
    else
        out_dir="$PREFIX"
        YODA=$(basename "$PREFIX")
        OUTFILE="$PREFIX/${YODA}.yoda"
    fi
    
    if [ -f "$OUTFILE" ]; then
        echo "Skipping: $OUTFILE already exists"
        return
    fi
    
    mapfile -t FILES < <(find "$PREFIX" -mindepth 2 -maxdepth 2 -type f \( -name '*.yoda' -o -name '*.yoda.gz' \))
    
    if [ "$NMAX" -gt 0 ] && [ "${#FILES[@]}" -gt "$NMAX" ]; then
        echo "Limiting to first $NMAX files (out of ${#FILES[@]} found)..."
        FILES=("${FILES[@]:0:$NMAX}")
    fi
    
    if [ "${#FILES[@]}" -eq 0 ]; then
        echo "Skipping $PREFIX: No .yoda/.yoda.gz files found in subdirectories."
    else
        if [ -n "$OUTPUT_DIR" ]; then
            mkdir -p "$out_dir"
        fi
        if [ "$CHUNK_SIZE" -gt 0 ]; then
            echo "Merging YODA files from all subdirectories into $OUTFILE using chunked mode..."
            merge_chunked "$out_dir" "$OUTFILE" "${FILES[@]}"
        else
            echo "Merging YODA files from all subdirectories into $OUTFILE..."
            if command -v yodamerge >/dev/null 2>&1; then
                yodamerge "${FILES[@]}" -o "$OUTFILE"
                if [ "$REMOVE_SUBDIRS" = true ] && [ -f "$OUTFILE" ] && [ -z "$OUTPUT_DIR" ]; then
                    for subdir in "$PREFIX"/*; do
                        if [ -d "$subdir" ]; then
                            echo "Removing $subdir..."
                            rm -rf "$subdir"
                        fi
                    done
                fi
            else
                echo "Error: yodamerge command not found. Please install YODA or adjust the script to point to the correct path!"
                exit 1
            fi
        fi
    fi
}

merge_chunked() {
    local dir="$1"
    local outfile="$2"
    shift 2
    local files=("$@")
    
    if command -v yodamerge >/dev/null 2>&1; then
        local total_files=${#files[@]}
        local num_chunks=$(( (total_files + CHUNK_SIZE - 1) / CHUNK_SIZE ))
        local chunk_parallel="$NPROC"
        if [ "$num_chunks" -lt "$chunk_parallel" ]; then
            chunk_parallel="$num_chunks"
        fi
        
        echo "Total files: $total_files, Chunk size: $CHUNK_SIZE, Number of chunks: $num_chunks, Parallel jobs: $NPROC"

        local temp_dir="$dir/.yodamerge_tmp"
        mkdir -p "$temp_dir"
        
        trap "rm -rf '$temp_dir'" EXIT INT TERM
        local chunk_num=0
        
        echo "Processing chunks in parallel batches of $chunk_parallel..."
        for ((i=0; i<total_files; i+=CHUNK_SIZE)); do
            local chunk_files=("${files[@]:i:CHUNK_SIZE}")
            local temp_file="$temp_dir/chunk_${chunk_num}.yoda"
            (
                echo "Merging chunk $chunk_num (${#chunk_files[@]} files) -> $(basename "$temp_file")"
                yodamerge "${chunk_files[@]}" -o "$temp_file"
            ) &
            
            chunk_num=$((chunk_num + 1))
            
            if (( chunk_num % chunk_parallel == 0 )); then
                echo "Waiting for batch to complete..."
                wait
            fi
        done
        
        echo "Waiting for final batch to complete..."
        wait

        echo "Merging $chunk_num temporary files into final output..."
        mapfile -t temp_files < <(find "$temp_dir" -name "chunk_*.yoda" | sort)
        
        if yodamerge "${temp_files[@]}" -o "$outfile"; then
            echo "Cleaning up temporary files..."
            rm -rf "$temp_dir"
            trap - EXIT INT TERM
            
            if [ "$REMOVE_SUBDIRS" = true ] && [ -f "$outfile" ] && [ -z "$OUTPUT_DIR" ]; then
                for subdir in "$dir"/*; do
                    if [ -d "$subdir" ] && [ "$subdir" != "$temp_dir" ]; then
                        echo "Removing $subdir..."
                        rm -rf "$subdir"
                    fi
                done
            fi
            echo "Successfully created $outfile"
        else
            echo "Error: Final merge failed, cleaning up temporary directory..."
            rm -rf "$temp_dir"
            trap - EXIT INT TERM
            return 1
        fi
    else
        echo "Error: yodamerge command not found. Please install YODA or adjust the script to point to the correct path!"
        exit 1
    fi
}

export -f merge_dir
export -f merge_flat
export -f merge_chunked
export REMOVE_SUBDIRS
export CHUNK_SIZE
export NPROC
export NMAX
export OUTPUT_DIR
export BASE_INPUT_DIR

ALL_NESTED_DIRS=()
ALL_FLAT_DIRS=()

for folder in "${FOLDERS[@]}"; do
    PREFIX="${folder%/}"
    if [ ! -d "$PREFIX" ]; then
        echo "Warning: No directory named $PREFIX! Skipping..."
        continue
    fi

    echo "Scanning input folder: $PREFIX"

    BASE_INPUT_DIR="$PREFIX"
    export BASE_INPUT_DIR

    has_nested_subdirs=false
    for dir in "$PREFIX"/*; do
        if [ -d "$dir" ] && [ "$(find "$dir" -mindepth 1 -maxdepth 1 -type d | wc -l)" -gt 0 ]; then
            has_nested_subdirs=true
            break
        fi
    done

    if [ "$has_nested_subdirs" = true ]; then
        nested_count=0
        while IFS= read -r dir; do
            ALL_NESTED_DIRS+=("$dir")
            nested_count=$((nested_count + 1))
        done < <(find "$PREFIX" -mindepth 1 -maxdepth 1 -type d)
    else
        ALL_FLAT_DIRS+=("$PREFIX")
    fi
done

TOTAL_DIRS=$(( ${#ALL_NESTED_DIRS[@]} + ${#ALL_FLAT_DIRS[@]} ))

if [ "$TOTAL_DIRS" -eq 0 ]; then
    echo "No valid directories found to merge."
    exit 0
fi

if [ "$CHUNK_SIZE" -gt 0 ]; then
    CHUNKED_DISPLAY="enabled (size: $CHUNK_SIZE)"
else
    CHUNKED_DISPLAY="disabled"
fi

if [ "$NMAX" -gt 0 ]; then
    NMAX_DISPLAY="$NMAX"
else
    NMAX_DISPLAY="all"
fi

if [ -n "$OUTPUT_DIR" ]; then
    OUTPUT_DIR_DISPLAY="$OUTPUT_DIR"
    if [ "$REMOVE_SUBDIRS" = true ]; then
        REMOVE_SUBDIRS_DISPLAY="ignored (with --output)"
    else
        REMOVE_SUBDIRS_DISPLAY="false"
    fi
else
    OUTPUT_DIR_DISPLAY="<in-place>"
    REMOVE_SUBDIRS_DISPLAY="$REMOVE_SUBDIRS"
fi

echo ""
echo "Merge configuration:"
echo "  input folders  : ${#FOLDERS[@]}"
echo "  total targets  : $TOTAL_DIRS"
echo "  parallel jobs  : $NPROC"
echo "  chunked mode   : $CHUNKED_DISPLAY"
echo "  nmax           : $NMAX_DISPLAY"
echo "  remove subdirs : $REMOVE_SUBDIRS_DISPLAY"
echo "  output dir     : $OUTPUT_DIR_DISPLAY"
echo ""

if [ ${#ALL_NESTED_DIRS[@]} -gt 0 ]; then
    NESTED_NPROC="$NPROC"
    if [ ${#ALL_NESTED_DIRS[@]} -lt "$NESTED_NPROC" ]; then
        NESTED_NPROC=${#ALL_NESTED_DIRS[@]}
    fi
    echo "Processing ${#ALL_NESTED_DIRS[@]} nested directories..."
    printf "%s\n" "${ALL_NESTED_DIRS[@]}" | xargs -n 1 -P "$NESTED_NPROC" bash -c 'merge_dir "$0"'
fi

if [ ${#ALL_FLAT_DIRS[@]} -gt 0 ]; then
    FLAT_NPROC="$NPROC"
    if [ ${#ALL_FLAT_DIRS[@]} -lt "$FLAT_NPROC" ]; then
        FLAT_NPROC=${#ALL_FLAT_DIRS[@]}
    fi
    echo "Processing ${#ALL_FLAT_DIRS[@]} flat directories..."
    printf "%s\n" "${ALL_FLAT_DIRS[@]}" | xargs -n 1 -P "$FLAT_NPROC" bash -c 'merge_flat "$0"'
fi

echo "Done! Merge run finished."
