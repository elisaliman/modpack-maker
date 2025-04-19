import requests
import os
from openai import OpenAI
import requests
import json
import zipfile
import os



def prompt_chatgpt(prompt:str, model_name:str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY_MOD"))

    response = client.responses.create(
        model=model_name,
        input=prompt
    )
    return response.output_text

# === Step 1: Get Prompt and Extract Keywords ===
def extract_keywords(prompt:str) -> list[str]:

    intstructions = (
    "Decide a fun name for this modpack and include it as the first entry for the keywords."
    "Extract exactly 6 other relevant keywords or short phrases from the following Minecraft modpack idea."
    "Focus on specific themes, creatures, features, or mechanics that would be useful when searching for individual mods."
    "Strictly 1 word phrases unless ABSOLUTLEY necessary to capture the idea"
    "If the prompt includes too little detail, extrapolate keywords from the implied themes or ideas."
    "Do not include generic terms like “minecraft”, “modpack”"
    "Return the result as 6 comma-separated, lowercase keywords or phrases."
    )
    full_prompt = f"{intstructions} Prompt: {prompt}"
    response = prompt_chatgpt(full_prompt, "gpt-4.1-mini")
    # banned_words = ["minecraft", "modpack"]
    # if contains_banned(response, banned_words):
    #     max_retries = 3
    #     warning_msg = f"Do not include ANY OF THESE WORDS in your output: {banned_words}"
    #     for attempt in range(max_retries):
    #         response = prompt_chatgpt(f"{warning_msg}. {full_prompt}", "gpt-4.1-mini")
    #         if not contains_banned(response, banned_words):
    #             break
    #     else:
    #         print("Failed to get clean output after retries.")
    print(response.split(","))
    return response.split(",")

def contains_banned(text:str, banned_words:list[str]) -> bool:
    return any(word in text.lower() for word in banned_words)

# === Step 2: Search Modrinth ===
def search_modrinth(keyword, version:str):
    url = "https://api.modrinth.com/v2/search"
    params = {
        "query": keyword,
        "facets": f'[["versions:{version}"]]',
        "limit": 5,
        "index": "downloads"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()["hits"]

# === Step 3: Assemble Modpack List ===
def assemble_modpack(keywords, version="1.20.1") -> list[dict]:
    mod_list = {}
    for keyword in keywords:
        results = search_modrinth(keyword, version)
        for mod in results:
            mod_id = mod["project_id"]
            if mod_id not in mod_list:
                mod_list[mod_id] = {
                    "project_id": mod_id,
                    "name": mod["title"],
                    "description": mod["description"],
                    "downloads": mod["downloads"],
                    "url": f"https://modrinth.com/mod/{mod['slug']}",
                    "slug": mod["slug"]
                }
    return list(mod_list.values())

# def finalize_list(mods: list[dict]) -> list[dict]:
#     instructions =  """
#     You will be given a list of Minecraft mods, each with a name and description.
#     Your task is to review all of the mods and select the ones that work well together
#     to create a cohesive and well-balanced modpack experience based on their themes, mechanics, and features.

#     - Group mods by theme (e.g. magic, tech, exploration, building, etc.) if needed.
#     - Remove mods that are redundant, clash in theme, or distract from the overall vision.
#     - If some mods rely on others to function well, keep them together.
#     - Prioritize synergy, balance, and player immersion.
#     - Only inlcude mods with a relatively high download count to ensure safety and quality
#         - relatively high download count is defined as 1000+ unless the change is a simple texture change or a tiny addition

#     Only include the mods that contribute meaningfully to the overall experience.

#     Return the selected mod names as a valid sequence of lowercase strings separated by this character: |
#     Do not include any extra text, explanations, or formatting.

#     """
#     mods_list = ""
#     for mod in mods:
#         mods_list += f"<mod>Mod Name:{mod['name']}. Description:{mod['description'][:300]}.</mod>"
#     full_prompt = f"{instructions}. Mod Descriptions: {mods_list}"
#     response = prompt_chatgpt(full_prompt, "gpt-4o")
#     mod_names = [name.strip().lower() for name in response.split("|")]
#     print(f"MOD NAMES = {response}\n\n\n")
#     final_mods = []
#     for mod in mods:
#         name_clean = mod['name'].strip().lower()
#         print(name_clean, name_clean in mod_names)
#         if name_clean in mod_names:
#             final_mods.append(mod)
#     return final_mods



# === CREATE MODPACK FILE ===
def add_mod_and_deps(project_id, mc_version, loader, added_ids, files):
    url = f"https://api.modrinth.com/v2/project/{project_id}/version"
    response = requests.get(url)
    response.raise_for_status()
    versions = response.json()

    for version in versions:
        if mc_version in version["game_versions"] and loader in version["loaders"]:
            file = version["files"][0]
            if project_id in added_ids:
                return  # already added
            files.append({
                "path": f"mods/{file['filename']}",
                "hashes": {
                    "sha1": file["hashes"]["sha1"],
                    "sha512": file["hashes"]["sha512"]
                },
                "downloads": [file["url"]],
                "fileSize": file["size"]
            })
            added_ids.add(project_id)

            # 🔁 Handle required dependencies
            for dep in version.get("dependencies", []):
                if dep["dependency_type"] == "required":
                    add_mod_and_deps(dep["project_id"], mc_version, loader, added_ids, files)

            return


# === Build a proper .mrpack manifest ===
def build_manifest(mod_entries, modpack_name, mc_version="1.20.1", loader="fabric"):
    files = []
    added_ids = set()

    for mod in mod_entries:
        add_mod_and_deps(mod["project_id"], mc_version, loader, added_ids, files)

    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": "ai-modpack",
        "name": modpack_name,
        "summary": "Modpack assembled with all required dependencies.",
        "dependencies": {
            "minecraft": mc_version,
            f"{loader}-loader": "latest"
        },
        "files": files
    }




def write_mrpack(manifest, output_path="output.mrpack"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    temp_path = "temp_pack/modrinth.index.json"
    os.makedirs("temp_pack", exist_ok=True)
    with open(temp_path, "w") as f:
        json.dump(manifest, f, indent=2)

    with zipfile.ZipFile(output_path, "w") as z:
        z.write(temp_path, arcname="modrinth.index.json")
    print(f"\n✅ Modpack written to: {output_path}")

def generate_modpack(prompt: str, output_path:str, version="1.20.1") -> list:
    keywords = extract_keywords(prompt)
    modpack_name, keywords = keywords[0], keywords[1:]
    mods = assemble_modpack(keywords, version)
    manifest = build_manifest(mods, modpack_name)
    write_mrpack(manifest, output_path)
    return mods
    # print("\nSuggested Mods:\n")
    # for mod in mods:
    #     print(f"{mod['name']} - {mod['url']}")
    #     print(f"Downloads: {mod['downloads']}")
    #     print(f"{mod['description'][:150]}...\n")

def get_modpack_description(mods: list[dict]) -> str:
    modpack_summary_prompt = (
    "You will be given a list of Minecraft mods, each with a name and short description.\n\n"
    "Your task is to analyze the list and write a brief but thoughtful overview of what kind of experience "
    "this modpack offers as a whole. Consider the themes, mechanics, and goals of the included mods.\n\n"
    "Describe what kind of world the player will be in, the challenges they might face, the gameplay loop, "
    "and what makes this modpack unique or interesting.\n\n"
    "Avoid listing the mods or their individual features — focus on the combined effect and the kind of "
    "adventure or atmosphere this pack creates.\n\n"
    "Write in 4-5 sentences, as if you're explaining the modpack to someone curious about downloading it."
    )
    mods_list = ""
    for mod in mods:
        mods_list += f"Mod Name:{mod['name']}. Description:{mod['description'][:300]}.\n"
    full_prompt = f"{modpack_summary_prompt} Here are the mod descriptions: {mods_list}"
    response = prompt_chatgpt(full_prompt, "gpt-4o")
    return response
