pub mod counter {
    static mut COUNT: u32 = 0;

    // "public API" functions we'll parse
    pub fn ping(n: u32) -> u32 {
        // not thread-safe; good enough for example
        unsafe { COUNT += n; COUNT }
    }

    pub fn get() -> u32 {
        unsafe { COUNT }
    }
}
