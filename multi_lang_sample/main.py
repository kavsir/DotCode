r"Set-Content -Path multi_lang_sample\main.py -Value @"


def helper():
    return {"name": "DotCode", "version": 1}


def format_result(data):
    return f"{data['name']} v{data['version']}"


def main():
    data = helper()
    result = format_result(data)
    print(result)


if __name__ == "__main__":
    main()
"@ -Encoding utf8"
