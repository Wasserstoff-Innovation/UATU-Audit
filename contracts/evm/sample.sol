// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Sample {
    uint256 public counter;
    mapping(address => uint256) public userCounts;
    
    event Ping(address indexed caller, uint256 n);
    event CountUpdated(address indexed user, uint256 oldCount, uint256 newCount);
    
    function ping(uint256 n) external {
        require(n > 0, "n must be positive");
        counter += n;
        userCounts[msg.sender] += n;
        emit Ping(msg.sender, n);
    }
    
    function getCount() external view returns (uint256) {
        return counter;
    }
    
    function getUserCount(address user) external view returns (uint256) {
        return userCounts[user];
    }
    
    function reset() external {
        counter = 0;
        emit CountUpdated(msg.sender, counter, 0);
    }
    
    function batchPing(uint256[] calldata amounts) external {
        for (uint256 i = 0; i < amounts.length; i++) {
            if (amounts[i] > 0) {
                counter += amounts[i];
                userCounts[msg.sender] += amounts[i];
                emit Ping(msg.sender, amounts[i]);
            }
        }
    }
}
