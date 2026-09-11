//
//  CryptoStorageLifecycleTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
import CryptoKit
@testable import PosteRestante

final class CryptoStorageLifecycleTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.storage.lifecycle"
	private var testAccount: String!
	private var sut: CryptoStorageManager!
	
	override func setUp() {
		super.setUp()
		testAccount = "test-storage-\(UUID().uuidString)"
		sut = CryptoStorageManager(service: testService, account: testAccount)
	}
	
	override func tearDown() {
		try? sut.deleteStorageKey()
		sut = nil
		testAccount = nil
		super.tearDown()
	}
	
	func test_getOrCreateMasterKey_generates256BitKey() throws {
		let key = try sut.getOrCreateMasterKey()
		let keyData = key.withUnsafeBytes { Data($0) }
		
		XCTAssertEqual(keyData.count, 32)
	}
	
	func test_getOrCreateMasterKey_returnsCachedKeyInRAM() throws {
		let initialKey = try sut.getOrCreateMasterKey()
		let cachedKey = try sut.getOrCreateMasterKey()
		
		let initialData = initialKey.withUnsafeBytes { Data($0) }
		let cachedData = cachedKey.withUnsafeBytes { Data($0) }
		
		XCTAssertEqual(initialData, cachedData)
	}
	
	func test_purgeMemoryCache_forcesReloadFromKeychain() throws {
		let originalKey = try sut.getOrCreateMasterKey()
		let originalData = originalKey.withUnsafeBytes { Data($0) }
		
		// Evict key from RAM
		sut.purgeMemoryCache()
		
		// Should reload the exact same key bytes from Keychain
		let reloadedKey = try sut.getOrCreateMasterKey()
		let reloadedData = reloadedKey.withUnsafeBytes { Data($0) }
		
		XCTAssertEqual(originalData, reloadedData)
	}
	
	func test_persistenceAcrossInstancesWithSameAccount() throws {
		let originalKey = try sut.getOrCreateMasterKey()
		let originalData = originalKey.withUnsafeBytes { Data($0) }
		
		// Separate instance pointing to the same Keychain item
		let secondaryManager = CryptoStorageManager(service: testService, account: testAccount)
		let loadedKey = try secondaryManager.getOrCreateMasterKey()
		let loadedData = loadedKey.withUnsafeBytes { Data($0) }
		
		XCTAssertEqual(originalData, loadedData)
	}
	
	func test_deleteStorageKey_purgesCacheAndKeychainEntry() throws {
		let originalKey = try sut.getOrCreateMasterKey()
		let originalData = originalKey.withUnsafeBytes { Data($0) }
		
		try sut.deleteStorageKey()
		
		// Subsequent call must generate a new key rather than returning deleted/cached data
		let freshKey = try sut.getOrCreateMasterKey()
		let freshData = freshKey.withUnsafeBytes { Data($0) }
		
		XCTAssertNotEqual(originalData, freshData)
	}
}
