
for country in ./minmax/*.json; do
  filename=$(basename -- "$country")
  countrycode="${filename%.*}"
  echo "Parsing ${country} having the code ${countrycode}"
  python ./compare_with_layerminmax.py "${countrycode}" "${country}"
done
