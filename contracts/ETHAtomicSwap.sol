// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ETHAtomicSwap - HTLC contract for KAS-ETH atomic swaps
 * Used by the autonomous AI swarm for cross-chain swaps
 */
contract ETHAtomicSwap {
    struct Swap {
        address payable initiator;
        address payable counterparty;
        uint256 amount;
        bytes32 secretHash;
        uint256 timelock;
        bool claimed;
        bool refunded;
    }

    mapping(bytes32 => Swap) public swaps;

    event Locked(bytes32 indexed swapId, address initiator, address counterparty, uint256 amount, bytes32 secretHash, uint256 timelock);
    event Claimed(bytes32 indexed swapId, bytes32 secret);
    event Refunded(bytes32 indexed swapId);

    /**
     * Lock ETH in HTLC
     * @param _secretHash SHA256 hash of the secret preimage
     * @param _counterparty Address that can claim with the secret
     * @param _timelock Seconds until refund is possible
     */
    function lock(bytes32 _secretHash, address payable _counterparty, uint256 _timelock) external payable {
        require(msg.value > 0, "Must send ETH");
        require(_counterparty != address(0), "Invalid counterparty");
        require(_timelock > 0, "Invalid timelock");

        bytes32 swapId = keccak256(abi.encodePacked(_secretHash, msg.sender, _counterparty));
        require(swaps[swapId].amount == 0, "Swap already exists");

        swaps[swapId] = Swap({
            initiator: payable(msg.sender),
            counterparty: _counterparty,
            amount: msg.value,
            secretHash: _secretHash,
            timelock: block.timestamp + _timelock,
            claimed: false,
            refunded: false
        });

        emit Locked(swapId, msg.sender, _counterparty, msg.value, _secretHash, block.timestamp + _timelock);
    }

    /**
     * Claim locked ETH by revealing the secret preimage
     * @param _secretHash The hash that was used to lock
     * @param _counterparty The counterparty address (to identify the swap)
     * @param _secret The preimage that hashes to secretHash
     */
    function claim(bytes32 _secretHash, address _counterparty, bytes32 _secret) external {
        bytes32 swapId = keccak256(abi.encodePacked(_secretHash, msg.sender, _counterparty));
        Swap storage s = swaps[swapId];

        require(s.amount > 0, "Swap does not exist");
        require(!s.claimed, "Already claimed");
        require(!s.refunded, "Already refunded");
        require(sha256(abi.encodePacked(_secret)) == s.secretHash, "Invalid secret");
        require(block.timestamp < s.timelock, "Timelock expired");

        s.claimed = true;
        
        (bool success, ) = s.counterparty.call{value: s.amount}("");
        require(success, "Transfer failed");

        emit Claimed(swapId, _secret);
    }

    /**
     * Refund locked ETH after timelock expires
     * @param _secretHash The hash that was used to lock
     * @param _counterparty The counterparty address (to identify the swap)
     */
    function refund(bytes32 _secretHash, address _counterparty) external {
        bytes32 swapId = keccak256(abi.encodePacked(_secretHash, msg.sender, _counterparty));
        Swap storage s = swaps[swapId];

        require(s.amount > 0, "Swap does not exist");
        require(!s.claimed, "Already claimed");
        require(!s.refunded, "Already refunded");
        require(block.timestamp >= s.timelock, "Timelock not expired");

        s.refunded = true;
        
        (bool success, ) = s.initiator.call{value: s.amount}("");
        require(success, "Transfer failed");

        emit Refunded(swapId);
    }

    /**
     * Get swap details
     */
    function getSwap(bytes32 _secretHash, address _counterparty) external view returns (
        address initiator,
        address counterparty,
        uint256 amount,
        bytes32 secretHash,
        uint256 timelock,
        bool claimed,
        bool refunded
    ) {
        bytes32 swapId = keccak256(abi.encodePacked(_secretHash, msg.sender, _counterparty));
        Swap storage s = swaps[swapId];
        return (s.initiator, s.counterparty, s.amount, s.secretHash, s.timelock, s.claimed, s.refunded);
    }
}
