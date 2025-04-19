from flask import Flask, render_template, request, send_file
from modpack_maker import generate_modpack, get_modpack_description
import os
import uuid

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    mods = []
    pack_file = None
    modpack_summary = None
    if request.method == 'POST':
        prompt = request.form['prompt']
        version = request.form['version']
        pack_id = str(uuid.uuid4())[:8]
        pack_path = f"packs/pack_{pack_id}.mrpack"
        mod_data = generate_modpack(prompt, pack_path, version=version)
        print("generate_modpack returned:")
        print(mod_data)
        mods = [{"name": mod["name"], "description": mod.get("description", "No description available.")} for mod in mod_data]
        pack_file = f"/download/{os.path.basename(pack_path)}"
        if mods:
            modpack_summary = get_modpack_description(mods)  # ✨ generate summary
    return render_template('index.html', mods=mods, pack_file=pack_file, summary=modpack_summary)

@app.route("/download/<filename>")
def download(filename):
    return send_file(f"packs/{filename}", as_attachment=True)

if __name__ == "__main__":
    os.makedirs("packs", exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=True)
