.PHONY: all data pipeline notebook clean
all:            ## tout relancer (équivalent à bash run_all.sh)
	bash run_all.sh
data:
	python src/download_data.py
pipeline: data
	python src/run_pipeline.py
notebook: pipeline
	python -m nbconvert --to notebook --execute --inplace sujet5_surveillance_compresseur.ipynb
clean:
	rm -rf results/*.csv results/*.json results/*.log results/*.gz results/figures
