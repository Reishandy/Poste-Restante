//
//  CryptoStoragError.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import Foundation

public enum CryptoStoragError: Error, LocalizedError, Equatable {
	case keychainOperationFailed(status: OSStatus)
	case encryptionFailed
	case decryptionFailed
	case deviceLocked
	case invalidKeySize(expected: Int, actual: Int)
	
	public var errorDescription: String? {
		switch self {
		case .keychainOperationFailed(let status):
			return "Keychain operation failed with OSStatus \(status)."
		case .encryptionFailed:
			return "Failed to encrypt plaintext payload into combined AES-GCM container."
		case .decryptionFailed:
			return "Decryption failed. Payload may be corrupt, tampered with, or sealed with a different key."
		case .deviceLocked:
			return "Protected data is unavailable while the device is locked."
		case .invalidKeySize(let expected, let actual):
			return "Invalid key size. Expected \(expected) bytes, got \(actual) bytes."
		}
	}
}
