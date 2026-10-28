"""Read image bytes on stdin and return OCR JSON; no remote requests."""
import contextlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import photo_reader

if __name__=='__main__':
    with contextlib.redirect_stdout(sys.stderr):
        if '--check' in sys.argv:
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from rapidocr_onnxruntime import RapidOCR
            RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
            result={'ok':True}
        else:
            data=sys.stdin.buffer.read(125_000_001)
            if len(data)>125_000_000:raise ValueError('Imagem grande demais.')
            with Image.open(io.BytesIO(data)) as image:
                if image.width*image.height>40_000_000:raise ValueError('Imagem grande demais.')
                text,scores,warnings=photo_reader.run_ocr(image,local_only=True)
                result={'text':text,'scores':scores,'warnings':warnings}
    print(json.dumps(result,ensure_ascii=True))
