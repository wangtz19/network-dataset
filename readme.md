# Generate Chinese QA datasets from raw documents
Some useful scripts for splitting long documents into shorter texts and generate QA based on each text chunk.

## Workflow
<img src="assets/workflow.jpg" alt="workflow">


### Splitter
Currently, raw documents are splitted in two modes: `normal mode` and `qa mode`:
*   `qa mode`: A raw document consisting of original qa data such as textbook exercises answers and FAQ manuals can be simply splitted into qa pairs without calling LLM API.
*   `normal mode`: Other documents are splitted based on their file formats correspondently. Up to now, 3 formats have been supported: `docx`, `pdf` and `txt`.
    *   `docx`: We prioritize parsing the `heading` and/or `outline` of a `docx` file, and divide the document into small text pieces using `heading` or `outline` as the boundary. If there exist no `heading` nor `outline` in the original file, it should be converted to plain texts (i.e. the `txt` format) and continues splitting. 
    *   `pdf`: Likewise,  we give priority to parsing a `pdf` file's `outline`, and convert it to plain texts for subsequent processing after failure.
    *   `txt`: Assuming that the input file has a good hierarchy e.g. chapters, text outlines, so it is possible to extract the table of contents (`toc`) from plain texts via regular expression.


### QA Generator
We use `text-davinci-003` and `gpt-3.5-turbo` to generate QA based on fact prompts derived from text chunks in a 2-stage way. At the first stage, several (3-5) questions are generated for each prompt instance, and corresponding answers are generated in the second stage.

To filter low-quality QA pairs, the following postprocessing operations should be executed:
*   Remove too short or too long QA pairs
*   Remove questions not ending with question mark
*   Remove answers not ending with period
*   Remove duplicated QA pairs
*   Convert traditional chinese characters to simplified chinese characters


### QA Evaluator
We adopt the framework of [GPTScore](https://github.com/jinlanfu/GPTScore) to evaluate our generated QA pairs.


## Usage
### Split documents
*   single file
```
python doc_splitter.py
--input <input-filename>
```

*   multiple files
```
python doc_splitter.py
--input_dir <input-directory>
```

*   qa mode
```
python doc_splitter.py
--input <input-qa-filename>
--mode qa
```

### Generate QA
Suppose fact prompts generated in last stage is stored at `<csv-filename>`, your OpenAI key path is `<key-path>`, and your proxy address is `<proxy>`
```
python qa_generator.py
--input <csv-filename>
--proxy <proxy>
--key_path <key_path>
```

### Evaluate QA
Suppose raw QAs generated in last stage is stored at `<raw-qa-filename>`
```
python qa_evaluator.py
--input <raw-qa-filename>
--proxy <proxy>
--key_path <key_path>
```  

### Augment Question
```
usage: python qa_augmentor.py [-h] --input INPUT [--output_format OUTPUT_FORMAT] [--proxy PROXY] [--key_path KEY_PATH]

optional arguments:
  -h, --help            show this help message and exit
  --input INPUT, -i INPUT
                        csv input file path
  --output_format OUTPUT_FORMAT, -o OUTPUT_FORMAT
                        output file format, csv or jsonl
  --proxy PROXY, -p PROXY
                        proxy address
  --key_path KEY_PATH, -k KEY_PATH
                        openai key path
```