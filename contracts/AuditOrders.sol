// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AuditOrders
 * @dev Minimal, safe USDC pull contract for UatuAudit orders
 * @author UatuAudit Team
 * 
 * Features:
 * - Fixed price: 100 USDC per audit
 * - Idempotent orders via salt
 * - Events for backend indexing
 * - Treasury management
 * - Base network optimized
 */

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function decimals() external view returns (uint8);
    function balanceOf(address account) external view returns (uint256);
}

contract AuditOrders {
    // Events
    event OrderPaid(
        bytes32 indexed orderId,
        address indexed payer,
        string repo,
        string commit,
        uint256 amount,
        address token,
        uint256 timestamp
    );
    
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event PriceUpdated(uint256 oldPrice, uint256 newPrice);

    // State variables
    address public treasury;
    IERC20 public immutable token; // USDC
    uint256 public price; // in token decimals (e.g., 100 * 10^6 for 100 USDC)
    
    // Access control
    address public owner;
    
    // Constants
    uint256 public constant MIN_PRICE = 1 * 10**6; // 1 USDC minimum
    uint256 public constant MAX_PRICE = 1000 * 10**6; // 1000 USDC maximum

    // Modifiers
    modifier onlyOwner() {
        require(msg.sender == owner, "AuditOrders: caller is not the owner");
        _;
    }

    modifier validPrice(uint256 _price) {
        require(_price >= MIN_PRICE && _price <= MAX_PRICE, "AuditOrders: invalid price");
        _;
    }

    /**
     * @dev Constructor
     * @param _treasury Treasury address to receive payments
     * @param _token USDC token address
     * @param _price Price in token decimals (e.g., 100 * 10^6 for 100 USDC)
     */
    constructor(
        address _treasury,
        address _token,
        uint256 _price
    ) validPrice(_price) {
        require(_treasury != address(0), "AuditOrders: treasury cannot be zero");
        require(_token != address(0), "AuditOrders: token cannot be zero");
        
        treasury = _treasury;
        token = IERC20(_token);
        price = _price;
        owner = msg.sender;
        
        emit TreasuryUpdated(address(0), _treasury);
        emit PriceUpdated(0, _price);
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
    ) external {
        require(bytes(repo).length > 0, "AuditOrders: repo cannot be empty");
        require(bytes(commit).length > 0, "AuditOrders: commit cannot be empty");
        require(salt != bytes32(0), "AuditOrders: salt cannot be zero");
        
        // Transfer USDC from user to treasury
        require(
            token.transferFrom(msg.sender, treasury, price),
            "AuditOrders: transfer failed"
        );
        
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
            block.timestamp
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
     * @dev Update treasury address (owner only)
     * @param newTreasury New treasury address
     */
    function updateTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "AuditOrders: treasury cannot be zero");
        require(newTreasury != treasury, "AuditOrders: treasury unchanged");
        
        address oldTreasury = treasury;
        treasury = newTreasury;
        
        emit TreasuryUpdated(oldTreasury, newTreasury);
    }

    /**
     * @dev Update price (owner only)
     * @param newPrice New price in token decimals
     */
    function updatePrice(uint256 newPrice) external onlyOwner validPrice(newPrice) {
        require(newPrice != price, "AuditOrders: price unchanged");
        
        uint256 oldPrice = price;
        price = newPrice;
        
        emit PriceUpdated(oldPrice, newPrice);
    }

    /**
     * @dev Transfer ownership (owner only)
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AuditOrders: new owner cannot be zero");
        require(newOwner != owner, "AuditOrders: owner unchanged");
        
        owner = newOwner;
    }

    /**
     * @dev Emergency withdrawal of stuck tokens (owner only)
     * @param tokenAddress Token address to withdraw
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(address tokenAddress, uint256 amount) external onlyOwner {
        require(tokenAddress != address(0), "AuditOrders: invalid token");
        require(amount > 0, "AuditOrders: amount must be positive");
        
        IERC20(tokenAddress).transferFrom(address(this), owner, amount);
    }

    /**
     * @dev Get contract information
     * @return _treasury Current treasury address
     * @return _token USDC token address
     * @return _price Current price in token decimals
     * @return _owner Current owner address
     */
    function getContractInfo() external view returns (
        address _treasury,
        address _token,
        uint256 _price,
        address _owner
    ) {
        return (treasury, address(token), price, owner);
    }
}
