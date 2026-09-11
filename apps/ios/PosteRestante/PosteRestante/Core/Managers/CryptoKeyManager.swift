//
//  CryptoKeyManager.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import Foundation
import CryptoKit
import UIKit

public final class CryptoKeyManager: Sendable {
	public static let shared = CryptoKeyManager()
	
	private let service = "id.reishandy.PosteRestante.identity"
	private let account: String
	
	// In-memory hot-path cache protected by lock
	private var cachedKey: SymmetricKey?
	private let lock = NSLock()
	private var observerToken: NSObjectProtocol?
	
	public init(account: String = "aes256-device") {
		self.account = account
		
		// Auto-eviction: wipe the 256-bit symmetric key from RAM immediately when screen locks
		self.observerToken = NotificationCenter.default.addObserver(
			forName: UIApplication.protectedDataWillBecomeUnavailableNotification,
			object: nil,
			queue: nil
		) { [weak self] _ in
			self?.purgeMemoryCache()
		}
	}
	
	// MARK: - Key Lifecycle
	
	/// Explicitly purges the symmetric key from RAM.
	public func purgeMemoryCache() {
		lock.lock()
		defer { lock.unlock() }
		cachedKey = nil
	}
	
	/// Returns the cached symmetric key, loads it from Keychain, or generates a new one.
	public func getOrCreateMasterKey() throws -> SymmetricKey {
		lock.lock()
		defer { lock.unlock() }
		
		if let key = cachedKey {
			return key
		}
		
		if let existingKeyData = try loadKeyDataFromKeychain() {
			let key = SymmetricKey(data: existingKeyData)
			self.cachedKey = key
			return key
		}
		
		// Generate a new 256-bit AES master key
		let newKey = SymmetricKey(size: .bits256)
		let keyData = newKey.withUnsafeBytes { Data($0) }
		try saveKeyDataToKeychain(keyData)
		self.cachedKey = newKey
		return newKey
	}
	
	/// Deletes the master key from the Keychain.
	public func deleteStorageKey() throws {
		lock.lock()
		defer { lock.unlock() }
		
		cachedKey = nil
		
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account
		]
		
		let status = SecItemDelete(query as CFDictionary)
		guard status == errSecSuccess || status == errSecItemNotFound else {
			throw CryptoStoragError.keychainOperationFailed(status: status)
		}
	}
	
	// MARK: - Functionality
	
	/// Encrypts plaintext into a combined AES-GCM container: 12-byte Nonce || Ciphertext || 16-byte Tag
	public func encrypt(_ plaintext: Data) throws -> Data {
		let key = try getOrCreateMasterKey()
		do {
			let sealedBox = try AES.GCM.seal(plaintext, using: key)
			guard let combined = sealedBox.combined else {
				throw CryptoStoragError.encryptionFailed
			}
			return combined
		} catch where !(error is CryptoStoragError) {
			throw CryptoStoragError.encryptionFailed
		}
	}
	
	/// Decrypts a combined AES-GCM container payload
	public func decrypt(_ combinedPayload: Data) throws -> Data {
		let key = try getOrCreateMasterKey()
		do {
			let sealedBox = try AES.GCM.SealedBox(combined: combinedPayload)
			return try AES.GCM.open(sealedBox, using: key)
		} catch {
			throw CryptoStoragError.decryptionFailed
		}
	}
	
	// MARK: - Helpers
	
	private func saveKeyDataToKeychain(_ data: Data) throws {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account,
			kSecValueData as String: data,
			kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
		]
		
		SecItemDelete(query as CFDictionary)
		
		let status = SecItemAdd(query as CFDictionary, nil)
		guard status == errSecSuccess else {
			throw CryptoStoragError.keychainOperationFailed(status: status)
		}
	}
	
	private func loadKeyDataFromKeychain() throws -> Data? {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account,
			kSecReturnData as String: true,
			kSecMatchLimit as String: kSecMatchLimitOne
		]
		
		var item: CFTypeRef?
		let status = SecItemCopyMatching(query as CFDictionary, &item)
		
		switch status {
		case errSecSuccess:
			guard let data = item as? Data else {
				throw CryptoStoragError.decryptionFailed
			}
			guard data.count == 32 else {
				throw CryptoStoragError.invalidKeySize(expected: 32, actual: data.count)
			}
			return data
		case errSecItemNotFound:
			return nil
		case errSecInteractionNotAllowed:
			// Thrown when trying to access WhenUnlocked items while device is locked
			throw CryptoStoragError.deviceLocked
		default:
			throw CryptoStoragError.keychainOperationFailed(status: status)
		}
	}
}
