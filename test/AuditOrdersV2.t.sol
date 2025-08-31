// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../contracts/AuditOrdersV2.sol";

/**
 * @title AuditOrdersV2Test
 * @dev Comprehensive tests for AuditOrdersV2 contract
 * @author UatuAudit Team
 */

// Mock USDC contract for testing
contract DummyUSDC is IERC20, IERC20Metadata {
    string public name = "USDC";
    string public symbol = "USDC";
    uint8 public override decimals = 6;
    
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public override allowance;
    uint256 public override totalSupply;
    
    function transfer(address to, uint256 amount) external override returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
    
    function approve(address spender, uint256 amount) external override returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }
    
    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        uint256 currentAllowance = allowance[from][msg.sender];
        require(currentAllowance >= amount, "Insufficient allowance");
        
        allowance[from][msg.sender] = currentAllowance - amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        
        return true;
    }
    
    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
    }
}

contract AuditOrdersV2Test is Test {
    DummyUSDC public usdc;
    AuditOrdersV2 public orders;
    
    address public payer = address(0xBEEF);
    address public treasury = address(0xCAFE);
    address public owner = address(this);
    
    uint256 public constant PRICE = 100e6; // 100 USDC
    string public constant REPO = "org/repo";
    string public constant COMMIT = "abcdef1234567890abcdef1234567890abcdef12";
    bytes32 public constant SALT = bytes32("test-salt-123");

    event OrderPaid(
        bytes32 indexed orderId,
        address indexed payer,
        string repo,
        string commit,
        uint256 amount,
        address token,
        uint256 chainId
    );

    function setUp() public {
        // Deploy mock USDC
        usdc = new DummyUSDC();
        
        // Deploy AuditOrders contract
        orders = new AuditOrdersV2(treasury, address(usdc), PRICE);
        
        // Setup test environment
        usdc.mint(payer, 200e6); // Give payer 200 USDC
        vm.prank(payer);
        usdc.approve(address(orders), type(uint256).max); // Approve unlimited spending
    }

    // ===== Basic Functionality Tests =====

    function testPayAndStart() public {
        // Expect OrderPaid event
        vm.expectEmit(true, true, false, true);
        emit OrderPaid(bytes32(0), payer, REPO, COMMIT, PRICE, address(usdc), block.chainid);
        
        // Execute payment
        vm.prank(payer);
        orders.payAndStart(REPO, COMMIT, SALT);
        
        // Verify balances
        assertEq(usdc.balanceOf(treasury), PRICE, "Treasury should receive payment");
        assertEq(usdc.balanceOf(payer), 100e6, "Payer should have remaining balance");
    }

    function testGetOrderId() public {
        bytes32 expectedOrderId = keccak256(abi.encode(payer, REPO, COMMIT, SALT, block.chainid));
        bytes32 actualOrderId = orders.getOrderId(payer, REPO, COMMIT, SALT);
        
        assertEq(actualOrderId, expectedOrderId, "Order ID should match expected");
    }

    function testCheckUserStatus() public {
        (bool hasAllowance, bool hasBalance) = orders.checkUserStatus(payer);
        
        assertTrue(hasAllowance, "User should have sufficient allowance");
        assertTrue(hasBalance, "User should have sufficient balance");
    }

    function testGetContractInfo() public {
        (address _treasury, address _token, uint256 _price, address _owner, bool _paused) = orders.getContractInfo();
        
        assertEq(_treasury, treasury, "Treasury should match");
        assertEq(_token, address(usdc), "Token should match");
        assertEq(_price, PRICE, "Price should match");
        assertEq(_owner, owner, "Owner should match");
        assertFalse(_paused, "Contract should not be paused");
    }

    // ===== Input Validation Tests =====

    function testPayAndStartEmptyRepo() public {
        vm.prank(payer);
        vm.expectRevert("AuditOrders: repo cannot be empty");
        orders.payAndStart("", COMMIT, SALT);
    }

    function testPayAndStartEmptyCommit() public {
        vm.prank(payer);
        vm.expectRevert("AuditOrders: commit cannot be empty");
        orders.payAndStart(REPO, "", SALT);
    }

    function testPayAndStartZeroSalt() public {
        vm.prank(payer);
        vm.expectRevert("AuditOrders: salt cannot be zero");
        orders.payAndStart(REPO, COMMIT, bytes32(0));
    }

    // ===== Pause Functionality Tests =====

    function testPause() public {
        orders.pause();
        assertTrue(orders.paused(), "Contract should be paused");
        
        vm.prank(payer);
        vm.expectRevert("Pausable: paused");
        orders.payAndStart(REPO, COMMIT, SALT);
    }

    function testUnpause() public {
        orders.pause();
        assertTrue(orders.paused(), "Contract should be paused");
        
        orders.unpause();
        assertFalse(orders.paused(), "Contract should be unpaused");
        
        // Should work again
        vm.prank(payer);
        orders.payAndStart(REPO, COMMIT, SALT);
    }

    function testPauseOnlyOwner() public {
        vm.prank(payer);
        vm.expectRevert("Ownable: caller is not the owner");
        orders.pause();
    }

    // ===== Admin Function Tests =====

    function testSetPrice() public {
        uint256 newPrice = 150e6; // 150 USDC
        
        orders.setPrice(newPrice);
        assertEq(orders.price(), newPrice, "Price should be updated");
    }

    function testSetPriceInvalid() public {
        vm.expectRevert("AuditOrders: invalid price");
        orders.setPrice(0); // Below minimum
        
        vm.expectRevert("AuditOrders: invalid price");
        orders.setPrice(2000e6); // Above maximum
    }

    function testSetPriceOnlyOwner() public {
        vm.prank(payer);
        vm.expectRevert("Ownable: caller is not the owner");
        orders.setPrice(150e6);
    }

    function testSetTreasury() public {
        address newTreasury = address(0xDEAD);
        
        orders.setTreasury(newTreasury);
        assertEq(orders.treasury(), newTreasury, "Treasury should be updated");
    }

    function testSetTreasuryZero() public {
        vm.expectRevert("AuditOrders: treasury cannot be zero");
        orders.setTreasury(address(0));
    }

    function testSetTreasuryOnlyOwner() public {
        vm.prank(payer);
        vm.expectRevert("Ownable: caller is not the owner");
        orders.setTreasury(address(0xDEAD));
    }

    // ===== Emergency Functions Tests =====

    function testEmergencyWithdraw() public {
        // Send some tokens to contract
        usdc.mint(address(orders), 50e6);
        
        uint256 balanceBefore = usdc.balanceOf(owner);
        orders.emergencyWithdraw(address(usdc), 50e6);
        uint256 balanceAfter = usdc.balanceOf(owner);
        
        assertEq(balanceAfter - balanceBefore, 50e6, "Owner should receive tokens");
    }

    function testEmergencyWithdrawOnlyOwner() public {
        vm.prank(payer);
        vm.expectRevert("Ownable: caller is not the owner");
        orders.emergencyWithdraw(address(usdc), 50e6);
    }

    // ===== View Function Tests =====

    function testGetPriceInUSD() public {
        uint256 priceInUSD = orders.getPriceInUSD();
        assertEq(priceInUSD, 100, "Price should be 100 USD");
    }

    function testIsOperational() public {
        assertTrue(orders.isOperational(), "Contract should be operational");
        
        orders.pause();
        assertFalse(orders.isOperational(), "Contract should not be operational when paused");
        
        orders.unpause();
        assertTrue(orders.isOperational(), "Contract should be operational again");
    }

    // ===== Edge Cases =====

    function testMultiplePayments() public {
        // First payment
        vm.prank(payer);
        orders.payAndStart(REPO, COMMIT, SALT);
        
        // Second payment with different salt
        vm.prank(payer);
        orders.payAndStart(REPO, COMMIT, bytes32("different-salt"));
        
        // Verify treasury received both payments
        assertEq(usdc.balanceOf(treasury), PRICE * 2, "Treasury should receive both payments");
    }

    function testReentrancyProtection() public {
        // This test ensures the nonReentrant modifier works
        // The contract should not allow reentrant calls to payAndStart
        
        // Deploy a malicious contract that tries to reenter
        ReentrantAttacker attacker = new ReentrantAttacker(orders, usdc);
        
        // Fund the attacker
        usdc.mint(address(attacker), PRICE);
        
        // This should fail due to reentrancy protection
        vm.expectRevert();
        attacker.attack(REPO, COMMIT, SALT);
    }
}

// Malicious contract for testing reentrancy protection
contract ReentrantAttacker {
    AuditOrdersV2 public orders;
    IERC20 public usdc;
    
    constructor(AuditOrdersV2 _orders, IERC20 _usdc) {
        orders = _orders;
        usdc = _usdc;
    }
    
    function attack(string calldata repo, string calldata commit, bytes32 salt) external {
        usdc.approve(address(orders), type(uint256).max);
        orders.payAndStart(repo, commit, salt);
    }
    
    // This function will be called during the transfer, attempting reentrancy
    function onERC20Received(address, address, uint256, bytes calldata) external returns (bytes4) {
        // Try to call payAndStart again (this should fail)
        orders.payAndStart("reentrant", "reentrant", bytes32("reentrant"));
        return this.onERC20Received.selector;
    }
}
