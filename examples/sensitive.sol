// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SensitiveContract {
    address public owner;
    uint256 public balance;
    
    constructor() {
        owner = msg.sender;
        balance = 1000;
    }
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }
    
    function ping() external {
        // harmless function
        balance += 1;
    }
    
    function withdraw(uint256 amount) external onlyOwner {
        // sensitive function - should be protected
        require(amount <= balance, "Insufficient balance");
        balance -= amount;
        // In a real contract, this would transfer ETH
    }
    
    function mint(uint256 amount) external onlyOwner {
        // sensitive function - should be protected
        balance += amount;
    }
    
    function setOwner(address newOwner) external onlyOwner {
        // sensitive function - should be protected
        owner = newOwner;
    }
}
