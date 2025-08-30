#![no_std]
use soroban_sdk::{contract, contractimpl, Address, Env, Symbol};

#[contract]
pub struct Counter;

#[contractimpl]
impl Counter {
    pub fn inc(env: Env, who: Address, by: i32) -> i32 {
        let key = (Symbol::new(&env, "count"), who.clone());
        let current: i32 = env.storage().persistent().get(&key).unwrap_or(0);
        let next = current + by;
        env.storage().persistent().set(&key, &next);
        next
    }

    pub fn get(env: Env, who: Address) -> i32 {
        let key = (Symbol::new(&env, "count"), who);
        env.storage().persistent().get(&key).unwrap_or(0)
    }
}
