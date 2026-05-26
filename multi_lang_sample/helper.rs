Set-Content -Path multi_lang_sample\helper.rs -Value @'
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

pub struct Calculator {
    pub value: i32,
}

impl Calculator {
    pub fn new() -> Self {
        Calculator { value: 0 }
    }
}
'@ -Encoding utf8