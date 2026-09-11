//
//  CryptoIdentityLifecycleTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
import CryptoKit
@testable import PosteRestante

final class CryptoIdentityLifecycleTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.lifecycle"
	private var testAccount: String!
	private var sut: CryptoIdentityManager!
	
	override func setUp() async throws {
		try await super.setUp()
		testAccount = "test-account-\(UUID().uuidString)"
		sut = CryptoIdentityManager(service: testService, account: testAccount)
	}
	
	override func tearDown() async throws {
		try? await sut.deleteIdentityKey()
		sut = nil
		testAccount = nil
		try await super.tearDown()
	}
	
	func test_getOrCreatePrivateKey_generatesValid32ByteKey() async throws {
		let key = try await sut.getOrCreatePrivateKey()
		XCTAssertEqual(key.rawRepresentation.count, 32)
	}
	
	func test_getOrCreatePrivateKey_isIdempotent() async throws {
		let firstKey = try await sut.getOrCreatePrivateKey()
		let secondKey = try await sut.getOrCreatePrivateKey()
		
		XCTAssertEqual(firstKey.rawRepresentation, secondKey.rawRepresentation)
	}
	
	func test_exportPublicKeyBytes_matchesPrivateKeyPublicKey() async throws {
		let privateKey = try await sut.getOrCreatePrivateKey()
		let exportedPublicKey = try await sut.exportPublicKeyBytes()
		
		XCTAssertEqual(exportedPublicKey.count, 32)
		XCTAssertEqual(exportedPublicKey, privateKey.publicKey.rawRepresentation)
	}
	
	func test_persistenceAcrossInstancesWithSameAccount() async throws {
		let originalKey = try await sut.getOrCreatePrivateKey()
		
		let secondaryManager = CryptoIdentityManager(service: testService, account: testAccount)
		let retrievedKey = try await secondaryManager.getOrCreatePrivateKey()
		
		XCTAssertEqual(originalKey.rawRepresentation, retrievedKey.rawRepresentation)
	}
	
	func test_deleteIdentityKey_removesKeyFromKeychain() async throws {
		_ = try await sut.getOrCreatePrivateKey()
		try await sut.deleteIdentityKey()
		
		// After deletion, a new call must write a fresh key to Keychain
		let newKey = try await sut.getOrCreatePrivateKey()
		let secondaryManager = CryptoIdentityManager(service: testService, account: testAccount)
		let persistedKey = try await secondaryManager.getOrCreatePrivateKey()
		
		XCTAssertEqual(newKey.rawRepresentation, persistedKey.rawRepresentation)
	}
}
