#!/bin/bash

OUTFILE="runs.txt"
APPEND=false
ANY_YODA=false
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        -o)
            shift
            if [ -z "${1-}" ]; then echo "-o requires an argument" >&2; exit 1; fi
            OUTFILE="$1"; shift ;;
        --add)
            APPEND=true; shift ;;
        --any-yoda)
            ANY_YODA=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--any-yoda] <folder1> [nsubfolders1] [<folder2> [nsubfolders2] ...]"
    echo "  <folder>      : Directory in which to create or list subfolders"
    echo "  [nsubfolders] : (Optional) Number of subfolders to create in each directory"
    echo "  -o outfile    : (Optional) Output filename (default: runs.txt)"
    echo "  --add         : (Optional) Append to existing outfile instead of overwriting"
    echo "  --any-yoda    : (Optional) Skip directories containing any .yoda file (not just name-matched ones)"
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

process_folder() {
    local PREFIX="${1%/}"
    local n="$2"
    if [ ! -d "$PREFIX" ]; then
        echo "Warning: No directory named $PREFIX! Skipping..."
        return 1
    fi

    if [ -z "$n" ]; then
        echo "Listing subdirectories in $PREFIX..."
        for dir in "$PREFIX"/*; do
            [ -d "$dir" ] || continue
            dir_name=$(basename "$dir")
            skip_dir=false
            if [ "$ANY_YODA" = true ] && [ -n "$(find "$dir" -maxdepth 1 -name "*.yoda" -type f)" ]; then
                skip_dir=true
            elif [ -f "$dir/${dir_name}.yoda.gz" ]; then
                skip_dir=true
            elif [ -f "$dir/${dir_name}.yoda" ]; then
                skip_dir=true
            fi

            if [ "$skip_dir" = false ]; then
                has_subdirs=false
                for subdir in "$dir"/*; do
                    if [ -d "$subdir" ]; then
                        has_subdirs=true
                        break
                    fi
                done
                if [ "$has_subdirs" = true ]; then
                    for subdir in "$dir"/*; do
                        [ -d "$subdir" ] || continue
                        subdir_name=$(basename "$subdir")
                        skip_subdir=false
                        if [ "$ANY_YODA" = true ] && [ -n "$(find "$subdir" -maxdepth 1 -name "*.yoda" -type f)" ]; then
                            skip_subdir=true
                        elif [ -f "$subdir/${subdir_name}.yoda.gz" ]; then
                            skip_subdir=true
                        fi
                        
                        if [ "$skip_subdir" = false ]; then
                            echo "$subdir" >> "$OUTFILE"
                        fi
                    done
                else
                    echo "$dir" >> "$OUTFILE"
                fi
            fi
        done
    else
        width=${#n}
        (( width < 2 )) && width=2
        
        has_subdirs=false
        for dir in "$PREFIX"/*; do
            if [ -d "$dir" ]; then
                has_subdirs=true
                break
            fi
        done

        if [ "$has_subdirs" = false ]; then
	    prefix_name=$(basename "$PREFIX")
	    skip_prefix=false
	    if [ "$ANY_YODA" = true ] && [ -n "$(find "$PREFIX" -maxdepth 1 -name "*.yoda" -type f)" ]; then
	        echo "Skipping $PREFIX (contains .yoda file)"
	        skip_prefix=true
	    elif [ -f "$PREFIX/${prefix_name}.yoda" ]; then
	        echo "Skipping $PREFIX (${prefix_name}.yoda already exists)"
	        skip_prefix=true
	    fi
	    
	    if [ "$skip_prefix" = false ]; then
	        echo "Creating $n subdirectories in $PREFIX..."
	        for ((j=0; j<n; j++)); do
	            sub_dir=$(printf "$PREFIX/%0${width}d" "$j")
	            mkdir "$sub_dir"
	            echo "Created: $sub_dir"
	            echo "$sub_dir" >> "$OUTFILE"
	        done
	    fi
        else
            echo "Creating $n subdirectories in each subdirectory of $PREFIX..."
            for dir in "$PREFIX"/*; do
                if [ -d "$dir" ] && [ "$(find "$dir" -mindepth 1 -maxdepth 1 -type d | wc -l)" -gt 0 ]; then
                    echo "Skipping $dir (already has subfolders)"
                    continue
                fi
                
                dir_name=$(basename "$dir")
                skip_dir=false
                if [ "$ANY_YODA" = true ] && [ -n "$(find "$dir" -maxdepth 1 -name "*.yoda" -type f)" ]; then
                    echo "Skipping $dir (contains .yoda file)"
                    skip_dir=true
                elif [ -f "$dir/${dir_name}.yoda" ]; then
                    echo "Skipping $dir (${dir_name}.yoda already exists)"
                    skip_dir=true
                fi
                
                if [ -d "$dir" ] && [ "$skip_dir" = false ]; then
                    for ((j=0; j<n; j++)); do
                        sub_dir=$(printf "$dir/%0${width}d" "$j")
                        mkdir "$sub_dir"
                        echo "Created: $sub_dir"
                        echo "$sub_dir" >> "$OUTFILE"
                    done
                fi
            done
        fi
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

echo "Done! Results written to $OUTFILE."

if [ -f "$OUTFILE" ]; then
    total_runs=$(wc -l < "$OUTFILE")
    echo "Total number of runs: $total_runs"
fi
