// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20, IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title AuditOrdersV2
 * @dev Enhanced security contract for UatuAudit payments
 * @author UatuAudit Team
 * 
 * Features:
 * - SafeERC20 for secure token transfers
 * - Pausable for emergency stops
 * - ReentrancyGuard for attack prevention
 * - Ownable2Step for secure ownership transfer
 * - Price and treasury management
 * - Event emission for backend indexing
 */
contract AuditOrdersV2 is Ownable2Step, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // Events
    event OrderPaid(
        bytes32 indexed orderId,
        address indexed payer,
        string repo,         // "owner/name"
        string commit,       // full SHA
        uint256 amount,      // in token decimals
        address token,       // USDC address
        uint256 chainId
    );
    event PriceChanged(uint256 oldPrice, uint256 newPrice);
    event TreasuryChanged(address oldTreasury, address newTreasury);
    event Paused(address account);
    event Unpaused(address account);

    // State variables
    IERC20 public immutable token;        // USDC
    uint8  public immutable tokenDecimals;
    address public treasury;              // payout wallet
    uint256 public price;                 // e.g., 100 * 10**6 for USDC
    
    // Constants
    uint256 public constant MIN_PRICE = 1 * 10**6;  // 1 USDC minimum
    uint256 public constant MAX_PRICE = 1000 * 10**6; // 1000 USDC maximum

    // Modifiers
    modifier validPrice(uint256 _price) {
        require(_price >= MIN_PRICE && _price <= MAX_PRICE, "AuditOrders: invalid price");
        _;
    }

    /**
     * @dev Constructor
     * @param _treasury Treasury address to receive payments
     * @param _token USDC token address
     * @param _price Price in token decimals (e.g., 100 * 10**6 for 100 USDC)
     */
    constructor(
        address _treasury,
        address _token,
        uint256 _price
    ) validPrice(_price) {
        require(_treasury != address(0), "AuditOrders: treasury cannot be zero");
        require(_token != address(0), "AuditOrders: token cannot be zero");
        
        token = IERC20(_token);
        tokenDecimals = IERC20Metadata(_token).decimals();
        treasury = _treasury;
        price = _price;
        
        _transferOwnership(msg.sender);
    }

    /**
     * @dev Pay for and start an audit
     * @param repo Repository identifier (e.g., "owner/name")
     * @param commit Commit SHA
     * @param salt Unique salt for idempotency
     */
    function payAndStart(
        string calldata repo,
        string calldata commit,
        bytes32 salt
    ) external whenNotPaused nonReentrant {
        require(bytes(repo).length > 0, "AuditOrders: repo cannot be empty");
        require(bytes(commit).length > 0, "AuditOrders: commit cannot be empty");
        require(salt != bytes32(0), "AuditOrders: salt cannot be zero");
        
        // Transfer USDC from user to treasury using SafeERC20
        token.safeTransferFrom(msg.sender, treasury, price);
        
        // Generate deterministic order ID
        bytes32 orderId = keccak256(
            abi.encode(
                msg.sender,
                repo,
                commit,
                salt,
                block.chainid
            )
        );
        
        // Emit event for backend indexing
        emit OrderPaid(
            orderId,
            msg.sender,
            repo,
            commit,
            price,
            address(token),
            block.chainid
        );
    }

    /**
     * @dev Get order ID without paying (for frontend preview)
     * @param payer User address
     * @param repo Repository identifier
     * @param commit Commit SHA
     * @param salt Unique salt
     * @return orderId Deterministic order ID
     */
    function getOrderId(
        address payer,
        string calldata repo,
        string calldata commit,
        bytes32 salt
    ) external view returns (bytes32 orderId) {
        return keccak256(
            abi.encode(
                payer,
                repo,
                commit,
                salt,
                block.chainid
            )
        );
    }

    /**
     * @dev Check if user has sufficient allowance and balance
     * @param user User address
     * @return hasAllowance Whether user has approved sufficient amount
     * @return hasBalance Whether user has sufficient balance
     */
    function checkUserStatus(address user) external view returns (bool hasAllowance, bool hasBalance) {
        hasAllowance = token.allowance(user, address(this)) >= price;
        hasBalance = token.balanceOf(user) >= price;
    }

    /**
     * @dev Get contract information
     * @return _treasury Current treasury address
     * @return _token USDC token address
     * @return _price Current price in token decimals
     * @return _owner Current owner address
     * @return _paused Whether contract is paused
     */
    function getContractInfo() external view returns (
        address _treasury,
        address _token,
        uint256 _price,
        address _owner,
        bool _paused
    ) {
        return (treasury, address(token), price, owner(), paused());
    }

    // --- Admin Functions ---

    /**
     * @dev Update price (owner only)
     * @param newPrice New price in token decimals
     */
    function setPrice(uint256 newPrice) external onlyOwner validPrice(newPrice) {
        require(newPrice != price, "AuditOrders: price unchanged");
        
        uint256 oldPrice = price;
        price = newPrice;
        
        emit PriceChanged(oldPrice, newPrice);
    }

    /**
     * @dev Update treasury address (owner only)
     * @param newTreasury New treasury address
     */
    function setTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "AuditOrders: treasury cannot be zero");
        require(newTreasury != treasury, "AuditOrders: treasury unchanged");
        
        address oldTreasury = treasury;
        treasury = newTreasury;
        
        emit TreasuryChanged(oldTreasury, newTreasury);
    }

    /**
     * @dev Pause contract (owner only)
     */
    function pause() external onlyOwner {
        _pause();
        emit Paused(msg.sender);
    }

    /**
     * @dev Unpause contract (owner only)
     */
    function unpause() external onlyOwner {
        _unpause();
        emit Unpaused(msg.sender);
    }

    /**
     * @dev Emergency withdrawal of stuck tokens (owner only)
     * @param tokenAddress Token address to withdraw
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(address tokenAddress, uint256 amount) external onlyOwner {
        require(tokenAddress != address(0), "AuditOrders: invalid token");
        require(amount > 0, "AuditOrders: amount must be positive");
        
        IERC20(tokenAddress).safeTransfer(owner(), amount);
    }

    /**
     * @dev Emergency withdrawal of ETH (owner only)
     */
    function emergencyWithdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "AuditOrders: no ETH to withdraw");
        
        (bool success, ) = owner().call{value: balance}("");
        require(success, "AuditOrders: ETH transfer failed");
    }

    // --- View Functions ---

    /**
     * @dev Get current price in human-readable format
     * @return priceInUSD Price in USD (assuming USDC = $1)
     */
    function getPriceInUSD() external view returns (uint256 priceInUSD) {
        return price / (10 ** tokenDecimals);
    }

    /**
     * @dev Check if contract is operational
     * @return operational Whether contract can accept payments
     */
    function isOperational() external view returns (bool operational) {
        return !paused() && treasury != address(0) && price > 0;
    }
}
