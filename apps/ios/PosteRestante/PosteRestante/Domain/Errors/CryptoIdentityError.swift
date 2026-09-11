//
//  CryptoIdentityError.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import Foundation

public enum CryptoIdentityError: Error, LocalizedError, Equatable {
	case keychainOperationFailed(status: OSStatus)
	case invalidKeySize(expected: Int, actual: Int)
	case invalidKeychainData
	case selfHandshakeNotPermitted
	case keyDerivationFailed
	case keyNotFound
	
	public var errorDescription: String? {
		switch self {
		case .keychainOperationFailed(let status):
			return "Keychain operation failed with OSStatus \(status)."
		case .invalidKeySize(let expected, let actual):
			return "Invalid key size. Expected \(expected) bytes, got \(actual) bytes."
		case .invalidKeychainData:
			return "Keychain returned data that could not be parsed as a valid key."
		case .selfHandshakeNotPermitted:
			return "Cannot perform key agreement with own public key."
		case .keyDerivationFailed:
			return "Failed to derive shared secret."
		case .keyNotFound:
			return "Identity key was not found in the Keychain."
		}
	}
}
